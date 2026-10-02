"""SQLite persistence via SQLAlchemy.

Tables:  users (User)  and  plans (WorkoutPlan, one row per user).
The original AI plan and the feedback-updated plan live in separate columns so both
versions are always available to the admin dashboard.
"""
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import (Column, DateTime, Float, ForeignKey, Integer, String, Text,
                        create_engine)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

from .config import settings

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _now() -> datetime:
    """Current UTC time (naive, as SQLite stores it)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=False)   # chosen by the user
    name = Column(String(60), nullable=False)
    age = Column(Integer, nullable=False)
    weight = Column(Float, nullable=False)
    goal = Column(String(200), nullable=False)
    intensity = Column(String(10), nullable=False)
    schedule = Column(Integer, default=7)                         # plan length in days
    created_at = Column(DateTime, default=_now)

    plan = relationship("WorkoutPlan", back_populates="user", uselist=False,
                        cascade="all, delete-orphan")


class WorkoutPlan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    original_plan = Column(Text, nullable=False)
    updated_plan = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="plan")


@contextmanager
def session_scope():
    """Open a session, commit on success, roll back on error, always close."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def _user_to_dict(user: User) -> dict:
    return {"id": user.id, "name": user.name, "age": user.age, "weight": user.weight,
            "goal": user.goal, "intensity": user.intensity}


# ---------------------------------------------------------------- users
def save_user(user_id: int, name: str, age: int, weight: float, goal: str, intensity: str) -> None:
    """Create the user, or update their details if the id already exists."""
    with session_scope() as db:
        existing = db.get(User, user_id)
        if existing:
            existing.name = name
            existing.age = age
            existing.weight = weight
            existing.goal = goal
            existing.intensity = intensity
        else:
            db.add(User(id=user_id, name=name, age=age, weight=weight, goal=goal,
                        intensity=intensity, schedule=7))


def get_user(user_id: int):
    with session_scope() as db:
        user = db.get(User, user_id)
        return _user_to_dict(user) if user else None


def get_all_users() -> list:
    with session_scope() as db:
        return [_user_to_dict(u) for u in db.query(User).order_by(User.id).all()]


def delete_user(user_id: int) -> bool:
    """Delete a user together with their plan. Returns False if the user does not exist."""
    with session_scope() as db:
        user = db.get(User, user_id)
        if not user:
            return False
        db.delete(user)
        return True


# ---------------------------------------------------------------- plans
def save_plan(user_id: int, plan: str) -> None:
    """Store a freshly generated plan. A new plan replaces the old one (and clears updates)."""
    with session_scope() as db:
        row = db.query(WorkoutPlan).filter(WorkoutPlan.user_id == user_id).first()
        if row:
            row.original_plan = plan
            row.updated_plan = None
            row.created_at = _now()
            row.updated_at = None
        else:
            db.add(WorkoutPlan(user_id=user_id, original_plan=plan))


def update_plan(user_id: int, updated_text: str) -> bool:
    """Save the feedback-based plan next to the original. Returns False if no plan exists."""
    with session_scope() as db:
        row = db.query(WorkoutPlan).filter(WorkoutPlan.user_id == user_id).first()
        if not row:
            return False
        row.updated_plan = updated_text
        row.updated_at = _now()
        return True


def get_original_plan(user_id: int):
    with session_scope() as db:
        row = db.query(WorkoutPlan).filter(WorkoutPlan.user_id == user_id).first()
        return row.original_plan if row else None


def get_current_plan(user_id: int):
    """Latest version of the plan: the updated one if it exists, otherwise the original."""
    with session_scope() as db:
        row = db.query(WorkoutPlan).filter(WorkoutPlan.user_id == user_id).first()
        if not row:
            return None
        return row.updated_plan or row.original_plan


def get_all_plans() -> list:
    with session_scope() as db:
        return [{"user_id": p.user_id, "original_plan": p.original_plan,
                 "updated_plan": p.updated_plan} for p in db.query(WorkoutPlan).all()]


def get_all_users_with_plans() -> list:
    """Rows for the admin dashboard: user details + original and updated plan."""
    plans = {p["user_id"]: p for p in get_all_plans()}
    rows = []
    for user in get_all_users():
        plan = plans.get(user["id"])
        rows.append({
            **user,
            "original_plan": plan["original_plan"] if plan else "N/A",
            "updated_plan": plan["updated_plan"] if plan and plan["updated_plan"] else "Not updated",
        })
    return rows
