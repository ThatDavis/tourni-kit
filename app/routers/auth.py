from fastapi import APIRouter, Request, Form, Depends, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import verify_password, create_access_token, get_password_hash
from app.models import User
from app.templates_engine import TemplateResponse

router = APIRouter()


@router.get("/admin/login")
async def login_page(request: Request):
    return TemplateResponse("admin/login.html", {"request": request, "error": None})


@router.post("/admin/login")
async def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return TemplateResponse("admin/login.html", {"request": request, "error": "Invalid credentials"})
    token = create_access_token({"sub": user.username})
    response = RedirectResponse(url="/admin/dashboard", status_code=302)
    response.set_cookie(key="access_token", value=token, httponly=True, max_age=86400, samesite="lax")
    return response


@router.post("/admin/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token")
    return response
