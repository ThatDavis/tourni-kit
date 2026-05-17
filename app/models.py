from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Boolean, Text, Index
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    transactions = relationship("InventoryTransaction", back_populates="user")
    sessions_created = relationship("BuildSession", back_populates="created_by")
    kit_builds_recorded = relationship("KitBuild", back_populates="recorded_by")
    invites_sent = relationship("UserInvite", back_populates="created_by")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    sort_order = Column(Integer, default=0)

    item_list = relationship("Item", back_populates="category", order_by="Item.name")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    name = Column(String, nullable=False)
    needed_per_kit = Column(Integer, default=1)
    source = Column(String, default="")
    cost_per_package = Column(Numeric(10, 4), default=0)
    qty_per_package = Column(Integer, default=1)
    cost_per_unit = Column(Numeric(10, 6), default=0)
    current_stock = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category = relationship("Category", back_populates="item_list")
    transactions = relationship("InventoryTransaction", back_populates="item", order_by="InventoryTransaction.created_at.desc()")


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    delta = Column(Integer, nullable=False)
    new_stock = Column(Integer, nullable=False)
    reason = Column(String, default="adjustment")
    note = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    item = relationship("Item", back_populates="transactions")
    user = relationship("User", back_populates="transactions")


class BuildSession(Base):
    __tablename__ = "build_sessions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    location = Column(String, default="")
    capacity = Column(Integer, default=10)
    waitlist_limit = Column(Integer, default=10)
    recommended_donation = Column(Numeric(10, 2), default=0)
    status = Column(String, default="scheduled")
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    created_by = relationship("User", back_populates="sessions_created")
    signups = relationship("SessionSignup", back_populates="session", order_by="SessionSignup.created_at")
    kit_builds = relationship("KitBuild", back_populates="session")


class SessionSignup(Base):
    __tablename__ = "session_signups"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("build_sessions.id"), nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    wants_stb = Column(Boolean, default=True)
    status = Column(String, default="confirmed")
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("BuildSession", back_populates="signups")
    kit_build = relationship("KitBuild", back_populates="signup", uselist=False)

    __table_args__ = (
        Index("ix_signup_session_email", "session_id", "email", unique=True),
    )


class KitBuild(Base):
    __tablename__ = "kit_builds"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("build_sessions.id"), nullable=False)
    signup_id = Column(Integer, ForeignKey("session_signups.id"), nullable=True)
    built_at = Column(DateTime, default=datetime.utcnow)
    recorded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    session = relationship("BuildSession", back_populates="kit_builds")
    signup = relationship("SessionSignup", back_populates="kit_build")
    recorded_by = relationship("User", back_populates="kit_builds_recorded")


class UserInvite(Base):
    __tablename__ = "user_invites"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, nullable=False)
    email = Column(String, nullable=False)
    username = Column(String, nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    created_by = relationship("User", back_populates="invites_sent")


class SiteSetting(Base):
    __tablename__ = "site_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(String, default="")
