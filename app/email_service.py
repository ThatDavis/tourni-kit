import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_TLS


def _can_send() -> bool:
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def send_email(to: str, subject: str, body_plain: str, body_html: str = ""):
    if not _can_send():
        print(f"[EMAIL LOGGED - no SMTP configured]\nTo: {to}\nSubject: {subject}\n{body_plain}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM or SMTP_USER
    msg["To"] = to

    msg.attach(MIMEText(body_plain, "plain"))
    if body_html:
        msg.attach(MIMEText(body_html, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        if SMTP_TLS:
            server.starttls(context=context)
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(msg["From"], [to], msg.as_string())


def send_signup_confirmation(to: str, name: str, session_title: str, session_datetime, location: str, status: str, waitlist_position: int = 0, wants_stb: bool = True):
    subject = f"IFAK Build Session Signup - {session_title}"
    if status == "confirmed":
        status_text = "You are confirmed!"
    else:
        status_text = f"You are on the waitlist (position #{waitlist_position})."

    stb_text = "with Stop The Bleed supplies" if wants_stb else "without Stop The Bleed supplies"

    body = f"""Hi {name},

You signed up for:
  Session: {session_title}
  When: {session_datetime}
  Where: {location}
  Status: {status_text}
  Kit type: {stb_text}

If you can no longer attend, please contact the organizers so we can open the spot to someone else.

Thanks!
"""
    send_email(to, subject, body)


def send_waitlist_promotion(to: str, name: str, session_title: str, session_datetime, location: str):
    subject = f"You're in! IFAK Build Session - {session_title}"
    body = f"""Hi {name},

Good news! A spot opened up and you have been moved from the waitlist to CONFIRMED for:
  Session: {session_title}
  When: {session_datetime}
  Where: {location}

See you there!
"""
    send_email(to, subject, body)
