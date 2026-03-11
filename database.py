"""
database.py — SQLAlchemy models for ISP backend
Tables: payments, pppoe_users, hotspot_vouchers, notifications
"""
import os
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, String, Integer, Float,
    DateTime, Boolean, Text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./isp.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite only
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── Models ──────────────────────────────────────────────────

class Payment(Base):
    __tablename__ = "payments"

    id              = Column(Integer, primary_key=True, index=True)
    checkout_id     = Column(String, unique=True, index=True)  # M-Pesa CheckoutRequestID
    mpesa_receipt   = Column(String, nullable=True)
    phone           = Column(String)
    amount          = Column(Float)
    plan            = Column(String)          # e.g. plan-1000 or hs-daily
    service_type    = Column(String)          # pppoe | hotspot
    status          = Column(String, default="pending")  # pending | paid | failed
    username        = Column(String, nullable=True)      # PPPoE username created
    voucher_code    = Column(String, nullable=True)      # Hotspot voucher
    created_at      = Column(DateTime, default=datetime.utcnow)
    paid_at         = Column(DateTime, nullable=True)


class PPPoEUser(Base):
    __tablename__ = "pppoe_users"

    id          = Column(Integer, primary_key=True, index=True)
    username    = Column(String, unique=True, index=True)
    phone       = Column(String)
    plan        = Column(String)
    active      = Column(Boolean, default=True)
    expires_at  = Column(DateTime, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
    comment     = Column(String, nullable=True)


class HotspotVoucher(Base):
    __tablename__ = "hotspot_vouchers"

    id          = Column(Integer, primary_key=True, index=True)
    code        = Column(String, unique=True, index=True)
    plan        = Column(String)
    phone       = Column(String, nullable=True)
    used        = Column(Boolean, default=False)
    used_at     = Column(DateTime, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id          = Column(Integer, primary_key=True, index=True)
    channel     = Column(String)   # whatsapp | gmail
    recipient   = Column(String)
    message     = Column(Text)
    success     = Column(Boolean)
    error       = Column(String, nullable=True)
    sent_at     = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
