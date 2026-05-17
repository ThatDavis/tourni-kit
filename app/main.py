from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import engine, Base
from app.seed import seed_from_csv
from app.settings import init_defaults
from app.routers import auth, admin, public


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    from sqlalchemy.orm import Session
    from app.database import SessionLocal
    db = SessionLocal()
    csv_path = Path(__file__).resolve().parent.parent / "IFAK_Share.csv"
    if csv_path.exists():
        seed_from_csv(db, csv_path)
    init_defaults(db)
    db.close()
    yield


app = FastAPI(title="Tourni-Kit", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(public.router)
