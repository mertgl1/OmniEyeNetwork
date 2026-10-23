from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    display_name = Column(String(128), nullable=True)
    email = Column(String(128), unique=True, nullable=True, index=True)
    hashed_password = Column(String(255), nullable=True)  # Nullable for AD users
    role = Column(String(32), nullable=False, default="viewer")  # admin, operator, viewer
    is_active = Column(Boolean, nullable=False, default=True)
    is_ad_user = Column(Boolean, nullable=False, default=False)

    last_login = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
