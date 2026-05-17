from datetime import datetime
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import BuildSession, SessionSignup, UserInvite
from app.auth import get_password_hash
from app.email_service import send_signup_confirmation, send_waitlist_promotion
from app.inventory_logic import get_kit_math
from app.templates_engine import TemplateResponse

router = APIRouter()


@router.get("/")
async def index(request: Request, db: Session = Depends(get_db)):
    sessions = db.query(BuildSession).filter(
        BuildSession.scheduled_at >= datetime.utcnow(),
        BuildSession.status != "cancelled"
    ).order_by(BuildSession.scheduled_at).all()
    math = get_kit_math(db)
    return TemplateResponse("public/index.html", {
        "request": request,
        "sessions": sessions,
        "base_donation": math["cost_no_stb"],
    })


@router.get("/about")
async def about_page(request: Request):
    return TemplateResponse("public/about.html", {
        "request": request,
    })


@router.get("/session/{session_id}")
async def session_public(request: Request, session_id: int, db: Session = Depends(get_db)):
    session = db.query(BuildSession).filter(BuildSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    confirmed_count = db.query(func.count(SessionSignup.id)).filter(
        SessionSignup.session_id == session_id,
        SessionSignup.status == "confirmed"
    ).scalar()
    waitlist_count = db.query(func.count(SessionSignup.id)).filter(
        SessionSignup.session_id == session_id,
        SessionSignup.status == "waitlist"
    ).scalar()
    spots_left = max(0, session.capacity - confirmed_count)
    math = get_kit_math(db)
    stb_cost = math["cost_with_stb"] - math["cost_no_stb"]
    return TemplateResponse("public/signup.html", {
        "request": request,
        "session": session,
        "spots_left": spots_left,
        "waitlist_count": waitlist_count,
        "base_donation": math["cost_no_stb"],
        "stb_cost": stb_cost,
        "error": None,
    })


@router.post("/session/{session_id}/signup")
async def session_signup_post(
    request: Request,
    session_id: int,
    name: str = Form(...),
    email: str = Form(...),
    wants_stb: str = Form("on"),
    db: Session = Depends(get_db),
):
    session = db.query(BuildSession).filter(BuildSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    confirmed_count = db.query(func.count(SessionSignup.id)).filter(
        SessionSignup.session_id == session_id,
        SessionSignup.status == "confirmed"
    ).scalar()
    waitlist_count = db.query(func.count(SessionSignup.id)).filter(
        SessionSignup.session_id == session_id,
        SessionSignup.status == "waitlist"
    ).scalar()
    spots_left = max(0, session.capacity - confirmed_count)

    existing = db.query(SessionSignup).filter(
        SessionSignup.session_id == session_id,
        SessionSignup.email == email,
    ).first()
    if existing and existing.status != "cancelled":
        math = get_kit_math(db)
        stb_cost = math["cost_with_stb"] - math["cost_no_stb"]
        return TemplateResponse("public/signup.html", {
            "request": request,
            "session": session,
            "spots_left": spots_left,
            "waitlist_count": waitlist_count,
            "base_donation": math["cost_no_stb"],
            "stb_cost": stb_cost,
            "error": "This email is already signed up for this session.",
        }, status_code=400)

    if spots_left > 0:
        status = "confirmed"
        waitlist_position = 0
    else:
        if waitlist_count >= session.waitlist_limit:
            math = get_kit_math(db)
            stb_cost = math["cost_with_stb"] - math["cost_no_stb"]
            return TemplateResponse("public/signup.html", {
                "request": request,
                "session": session,
                "spots_left": 0,
                "waitlist_count": waitlist_count,
                "base_donation": math["cost_no_stb"],
                "stb_cost": stb_cost,
                "error": "This session is full and the waitlist is also full.",
            }, status_code=400)
        status = "waitlist"
        waitlist_position = waitlist_count + 1

    signup = SessionSignup(
        session_id=session_id,
        name=name,
        email=email,
        wants_stb=(wants_stb == "on"),
        status=status,
    )
    db.add(signup)
    db.commit()

    send_signup_confirmation(
        to=email,
        name=name,
        session_title=session.title,
        session_datetime=session.scheduled_at,
        location=session.location,
        status=status,
        waitlist_position=waitlist_position,
        wants_stb=(wants_stb == "on"),
    )

    math = get_kit_math(db)
    stb_cost = math["cost_with_stb"] - math["cost_no_stb"]
    return TemplateResponse("public/success.html", {
        "request": request,
        "session": session,
        "status": status,
        "waitlist_position": waitlist_position,
        "name": name,
        "wants_stb": (wants_stb == "on"),
        "base_donation": math["cost_no_stb"],
        "stb_cost": stb_cost,
    })


# ─── Invite Acceptance ──────────────────────────────────────────────────────

@router.get("/accept-invite/{token}")
async def accept_invite_page(request: Request, token: str, db: Session = Depends(get_db)):
    invite = db.query(UserInvite).filter(UserInvite.token == token, UserInvite.used_at == None).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid or expired invite")
    return TemplateResponse("public/accept_invite.html", {
        "request": request,
        "invite": invite,
        "error": None,
    })


@router.post("/accept-invite/{token}")
async def accept_invite_post(
    request: Request,
    token: str,
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    invite = db.query(UserInvite).filter(UserInvite.token == token, UserInvite.used_at == None).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid or expired invite")

    if password != confirm_password:
        return TemplateResponse("public/accept_invite.html", {
            "request": request,
            "invite": invite,
            "error": "Passwords do not match.",
        }, status_code=400)

    if len(password) < 6:
        return TemplateResponse("public/accept_invite.html", {
            "request": request,
            "invite": invite,
            "error": "Password must be at least 6 characters.",
        }, status_code=400)

    existing = db.query(User).filter((User.username == invite.username) | (User.email == invite.email)).first()
    if existing:
        return TemplateResponse("public/accept_invite.html", {
            "request": request,
            "invite": invite,
            "error": "Username or email already in use.",
        }, status_code=400)

    user = User(
        username=invite.username,
        email=invite.email,
        hashed_password=get_password_hash(password),
        is_admin=True,
    )
    db.add(user)
    invite.used_at = datetime.utcnow()
    db.add(invite)
    db.commit()

    return RedirectResponse(url="/admin/login", status_code=302)
