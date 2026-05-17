from sqlalchemy.orm import Session
from app.models import SiteSetting

DEFAULTS = {
    "site_title": "Tourni-Kit",
    "about_content": "<p>Welcome! We organize group IFAK builds at cost. Check back for upcoming sessions.</p>",
    "theme_primary": "#0057B7",
    "theme_secondary": "#E4002B",
    "theme_accent": "#41B6E6",
    "theme_bg": "#F7F9FC",
    "theme_card": "#FFFFFF",
    "theme_text": "#1A1D23",
    "theme_text_secondary": "#4A5568",
}


def get_setting(db: Session, key: str) -> str:
    s = db.query(SiteSetting).filter(SiteSetting.key == key).first()
    if s:
        return s.value
    return DEFAULTS.get(key, "")


def get_all_settings(db: Session) -> dict:
    result = dict(DEFAULTS)
    for s in db.query(SiteSetting).all():
        result[s.key] = s.value
    return result


def set_setting(db: Session, key: str, value: str):
    s = db.query(SiteSetting).filter(SiteSetting.key == key).first()
    if s:
        s.value = value
    else:
        s = SiteSetting(key=key, value=value)
        db.add(s)
    db.commit()


def init_defaults(db: Session):
    for key, value in DEFAULTS.items():
        existing = db.query(SiteSetting).filter(SiteSetting.key == key).first()
        if not existing:
            db.add(SiteSetting(key=key, value=value))
    db.commit()
