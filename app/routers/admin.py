from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
import secrets

from app.database import get_db
from app.auth import require_admin, get_password_hash
from app.models import User, Category, Item, InventoryTransaction, BuildSession, SessionSignup, KitBuild, UserInvite
from app.inventory_logic import get_kit_math, consume_kit_stock, add_inventory
from app.email_service import send_waitlist_promotion
from app.templates_engine import TemplateResponse
from app.settings import get_all_settings, set_setting

router = APIRouter()


@router.get("/admin/dashboard")
async def dashboard(request: Request, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    math = get_kit_math(db)
    upcoming = db.query(BuildSession).filter(BuildSession.scheduled_at >= datetime.utcnow()).order_by(BuildSession.scheduled_at).limit(5).all()
    total_kits_built = db.query(func.count(KitBuild.id)).scalar()
    total_sessions = db.query(func.count(BuildSession.id)).scalar()
    return TemplateResponse("admin/dashboard.html", {
        "request": request,
        "user": user,
        "math": math,
        "upcoming": upcoming,
        "total_kits_built": total_kits_built,
        "total_sessions": total_sessions,
    })


# ─── Inventory ──────────────────────────────────────────────────────────────

@router.get("/admin/inventory")
async def inventory_list(request: Request, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    categories = db.query(Category).order_by(Category.sort_order).all()
    return TemplateResponse("admin/inventory.html", {
        "request": request,
        "user": user,
        "categories": categories,
    })


@router.get("/admin/inventory/{item_id}")
async def inventory_edit_page(request: Request, item_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    categories = db.query(Category).order_by(Category.sort_order).all()
    return TemplateResponse("admin/item_edit.html", {
        "request": request,
        "user": user,
        "item": item,
        "categories": categories,
    })


@router.post("/admin/inventory/{item_id}")
async def inventory_edit_post(
    request: Request,
    item_id: int,
    name: str = Form(...),
    category_id: int = Form(...),
    needed_per_kit: int = Form(1),
    source: str = Form(""),
    cost_per_package: str = Form("0"),
    qty_per_package: int = Form(1),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    item.name = name
    item.category_id = category_id
    item.needed_per_kit = needed_per_kit
    item.source = source
    item.cost_per_package = Decimal(cost_per_package) if cost_per_package else Decimal("0")
    item.qty_per_package = qty_per_package
    if item.qty_per_package > 0:
        item.cost_per_unit = item.cost_per_package / Decimal(item.qty_per_package)
    db.commit()
    return RedirectResponse(url="/admin/inventory", status_code=302)


@router.post("/admin/inventory/{item_id}/add-stock")
async def inventory_add_stock(
    request: Request,
    item_id: int,
    packages: int = Form(...),
    note: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    add_inventory(db, item_id, user.id, packages, reason="purchase", note=note)
    return RedirectResponse(url=f"/admin/inventory/{item_id}", status_code=302)


# ─── Categories ─────────────────────────────────────────────────────────────

@router.post("/admin/categories")
async def category_create(
    request: Request,
    name: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    max_order = db.query(func.max(Category.sort_order)).scalar() or 0
    cat = Category(name=name, sort_order=max_order + 1)
    db.add(cat)
    db.commit()
    return RedirectResponse(url="/admin/inventory", status_code=302)


@router.post("/admin/categories/{cat_id}/delete")
async def category_delete(
    request: Request,
    cat_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    cat = db.query(Category).filter(Category.id == cat_id).first()
    if cat:
        # Delete all items in category first
        db.query(Item).filter(Item.category_id == cat_id).delete()
        db.delete(cat)
        db.commit()
    return RedirectResponse(url="/admin/inventory", status_code=302)


# ─── Items ──────────────────────────────────────────────────────────────────

@router.get("/admin/items/new")
async def item_new_page(request: Request, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    categories = db.query(Category).order_by(Category.sort_order).all()
    return TemplateResponse("admin/item_new.html", {
        "request": request,
        "user": user,
        "categories": categories,
    })


@router.post("/admin/items")
async def item_create(
    request: Request,
    name: str = Form(...),
    category_id: int = Form(...),
    needed_per_kit: int = Form(1),
    source: str = Form(""),
    cost_per_package: str = Form("0"),
    qty_per_package: int = Form(1),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    cpp = Decimal(cost_per_package) if cost_per_package else Decimal("0")
    qpp = qty_per_package or 1
    cpu = cpp / Decimal(qpp) if qpp > 0 else Decimal("0")
    item = Item(
        category_id=category_id,
        name=name,
        needed_per_kit=needed_per_kit or 1,
        source=source,
        cost_per_package=cpp,
        qty_per_package=qpp,
        cost_per_unit=cpu,
        current_stock=0,
    )
    db.add(item)
    db.commit()
    return RedirectResponse(url="/admin/inventory", status_code=302)


# ─── Audit Log ──────────────────────────────────────────────────────────────

@router.get("/admin/audit-log")
async def audit_log(request: Request, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    txs = db.query(InventoryTransaction).order_by(InventoryTransaction.created_at.desc()).limit(200).all()
    return TemplateResponse("admin/audit_log.html", {
        "request": request,
        "user": user,
        "transactions": txs,
    })


# ─── Sessions ───────────────────────────────────────────────────────────────

@router.get("/admin/sessions")
async def sessions_list(request: Request, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    sessions = db.query(BuildSession).order_by(BuildSession.scheduled_at.desc()).all()
    return TemplateResponse("admin/sessions.html", {
        "request": request,
        "user": user,
        "sessions": sessions,
    })


@router.get("/admin/sessions/new")
async def sessions_new_page(request: Request, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return TemplateResponse("admin/session_new.html", {
        "request": request,
        "user": user,
    })


@router.post("/admin/sessions")
async def sessions_create(
    request: Request,
    title: str = Form(...),
    scheduled_at: str = Form(...),
    location: str = Form(""),
    capacity: int = Form(10),
    waitlist_limit: int = Form(10),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    math = get_kit_math(db)
    session = BuildSession(
        title=title,
        scheduled_at=datetime.fromisoformat(scheduled_at),
        location=location,
        capacity=capacity,
        waitlist_limit=waitlist_limit,
        recommended_donation=math["cost_no_stb"],
        status="scheduled",
        created_by_id=user.id,
    )
    db.add(session)
    db.commit()
    return RedirectResponse(url="/admin/sessions", status_code=302)


@router.get("/admin/sessions/{session_id}")
async def session_detail(request: Request, session_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    session = db.query(BuildSession).filter(BuildSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    confirmed = [s for s in session.signups if s.status == "confirmed"]
    waitlist = [s for s in session.signups if s.status == "waitlist"]
    attended = [s for s in session.signups if s.status == "attended"]
    kit_builds = {kb.signup_id for kb in session.kit_builds}
    math = get_kit_math(db)
    return TemplateResponse("admin/session_detail.html", {
        "request": request,
        "user": user,
        "session": session,
        "confirmed": confirmed,
        "waitlist": waitlist,
        "attended": attended,
        "kit_builds": kit_builds,
        "base_donation": math["cost_no_stb"],
    })


@router.post("/admin/sessions/{session_id}/build")
async def session_build_kit(
    request: Request,
    session_id: int,
    signup_id: int = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    session = db.query(BuildSession).filter(BuildSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    signup = db.query(SessionSignup).filter(SessionSignup.id == signup_id, SessionSignup.session_id == session_id).first()
    if not signup:
        raise HTTPException(status_code=404, detail="Signup not found")
    if signup.status in ("cancelled",):
        raise HTTPException(status_code=400, detail="Signup is cancelled")

    existing = db.query(KitBuild).filter(KitBuild.signup_id == signup_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Kit already recorded for this signup")

    ok = consume_kit_stock(db, user.id, note=f"kit build for session {session.title}")
    if not ok:
        raise HTTPException(status_code=400, detail="Insufficient inventory to build a kit")

    kb = KitBuild(
        session_id=session_id,
        signup_id=signup_id,
        recorded_by_id=user.id,
    )
    db.add(kb)
    signup.status = "attended"
    db.add(signup)
    db.commit()
    return RedirectResponse(url=f"/admin/sessions/{session_id}", status_code=302)


@router.post("/admin/sessions/{session_id}/cancel-signup")
async def session_cancel_signup(
    request: Request,
    session_id: int,
    signup_id: int = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    session = db.query(BuildSession).filter(BuildSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    signup = db.query(SessionSignup).filter(SessionSignup.id == signup_id, SessionSignup.session_id == session_id).first()
    if not signup:
        raise HTTPException(status_code=404, detail="Signup not found")

    was_confirmed = signup.status == "confirmed"
    signup.status = "cancelled"
    db.add(signup)
    db.commit()

    if was_confirmed:
        next_waitlist = db.query(SessionSignup).filter(
            SessionSignup.session_id == session_id,
            SessionSignup.status == "waitlist"
        ).order_by(SessionSignup.created_at).first()
        if next_waitlist:
            next_waitlist.status = "confirmed"
            db.add(next_waitlist)
            db.commit()
            send_waitlist_promotion(
                to=next_waitlist.email,
                name=next_waitlist.name,
                session_title=session.title,
                session_datetime=session.scheduled_at,
                location=session.location,
            )

    return RedirectResponse(url=f"/admin/sessions/{session_id}", status_code=302)


@router.post("/admin/sessions/{session_id}/complete")
async def session_complete(
    request: Request,
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    session = db.query(BuildSession).filter(BuildSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.status = "completed"
    db.commit()
    return RedirectResponse(url=f"/admin/sessions/{session_id}", status_code=302)


# ─── User Management ────────────────────────────────────────────────────────

@router.get("/admin/users")
async def users_list(request: Request, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    invites = db.query(UserInvite).order_by(UserInvite.created_at.desc()).all()
    return TemplateResponse("admin/users.html", {
        "request": request,
        "user": user,
        "users": users,
        "invites": invites,
    })


@router.post("/admin/users/invite")
async def users_invite(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    existing = db.query(User).filter((User.username == username) | (User.email == email)).first()
    if existing:
        return TemplateResponse("admin/users.html", {
            "request": request,
            "user": admin_user,
            "users": db.query(User).order_by(User.created_at.desc()).all(),
            "invites": db.query(UserInvite).order_by(UserInvite.created_at.desc()).all(),
            "error": "A user with that username or email already exists.",
        }, status_code=400)

    token = secrets.token_urlsafe(32)
    invite = UserInvite(
        token=token,
        email=email,
        username=username,
        created_by_id=admin_user.id,
    )
    db.add(invite)
    db.commit()

    from app.email_service import send_email
    from app.config import BASE_URL
    accept_url = f"{BASE_URL}/accept-invite/{token}"
    body = f"""Hello,

You have been invited to join the Tourni-Kit admin team.

Username: {username}
Click here to set your password and accept the invite:
{accept_url}

If you did not expect this invitation, you can safely ignore it.
"""
    send_email(email, "Tourni-Kit - Admin Invite", body)

    return RedirectResponse(url="/admin/users", status_code=302)


@router.post("/admin/users/{user_id}/delete")
async def user_delete(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    target = db.query(User).filter(User.id == user_id).first()
    if target and target.id != admin_user.id:
        db.delete(target)
        db.commit()
    return RedirectResponse(url="/admin/users", status_code=302)


# ─── Settings ───────────────────────────────────────────────────────────────

@router.get("/admin/settings")
async def settings_page(request: Request, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    settings = get_all_settings(db)
    return TemplateResponse("admin/settings.html", {
        "request": request,
        "user": user,
        "settings": settings,
    })


@router.post("/admin/settings")
async def settings_post(
    request: Request,
    site_title: str = Form(""),
    about_content: str = Form(""),
    theme_primary: str = Form("#0057B7"),
    theme_secondary: str = Form("#E4002B"),
    theme_accent: str = Form("#41B6E6"),
    theme_bg: str = Form("#F7F9FC"),
    theme_card: str = Form("#FFFFFF"),
    theme_text: str = Form("#1A1D23"),
    theme_text_secondary: str = Form("#4A5568"),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    set_setting(db, "site_title", site_title)
    set_setting(db, "about_content", about_content)
    set_setting(db, "theme_primary", theme_primary)
    set_setting(db, "theme_secondary", theme_secondary)
    set_setting(db, "theme_accent", theme_accent)
    set_setting(db, "theme_bg", theme_bg)
    set_setting(db, "theme_card", theme_card)
    set_setting(db, "theme_text", theme_text)
    set_setting(db, "theme_text_secondary", theme_text_secondary)
    return RedirectResponse(url="/admin/settings", status_code=302)
