from jinja2 import Environment, FileSystemLoader
from starlette.templating import _TemplateResponse
from starlette.requests import Request
from app.database import SessionLocal
from app.settings import get_all_settings

env = Environment(loader=FileSystemLoader("app/templates"))


def TemplateResponse(name: str, context: dict, status_code: int = 200):
    template = env.get_template(name)
    request = context.get("request")
    if request is None:
        raise ValueError("context must include a 'request' key")

    # Inject site settings into every template
    db = SessionLocal()
    try:
        settings = get_all_settings(db)
        context["settings"] = settings
    finally:
        db.close()

    return _TemplateResponse(
        template=template,
        context=context,
        status_code=status_code,
        headers=None,
        media_type="text/html; charset=utf-8",
        background=None,
    )
