#!/usr/bin/env python3
import sys
import getpass
from pathlib import Path

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import SessionLocal, engine, Base
from app.models import User
from app.auth import get_password_hash


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    username = input("Username: ").strip()
    email = input("Email: ").strip()
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm Password: ")
    if password != confirm:
        print("Passwords do not match.")
        sys.exit(1)

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        print(f"User '{username}' already exists.")
        sys.exit(1)

    user = User(
        username=username,
        email=email,
        hashed_password=get_password_hash(password),
        is_admin=True,
    )
    db.add(user)
    db.commit()
    print(f"Admin user '{username}' created.")
    db.close()


if __name__ == "__main__":
    main()
