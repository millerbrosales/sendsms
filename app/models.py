from sqlalchemy import Column, Integer, String, Date, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from .db import Base

def utcnow():
    return datetime.now(timezone.utc)

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    order_id = Column(String(150), nullable=True, index=True)
    customer_name = Column(String(200), nullable=False)
    phone_e164 = Column(String(30), nullable=False, index=True)
    rep_name = Column(String(150), nullable=True)
    install_date = Column(Date, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    messages = relationship("ScheduledMessage", back_populates="customer", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("order_id", name="uq_customer_order_id"),
    )

class ScheduledMessage(Base):
    __tablename__ = "scheduled_messages"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    message_type = Column(String(50), nullable=False)
    body = Column(Text, nullable=False)
    scheduled_for = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(String(30), default="scheduled", nullable=False, index=True)
    twilio_sid = Column(String(80), nullable=True, unique=True, index=True)
    error = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    customer = relationship("Customer", back_populates="messages")

    __table_args__ = (
        UniqueConstraint("customer_id", "message_type", name="uq_customer_message_type"),
    )

class InboundMessage(Base):
    __tablename__ = "inbound_messages"
    id = Column(Integer, primary_key=True)
    twilio_sid = Column(String(80), unique=True, nullable=False, index=True)
    from_number = Column(String(30), nullable=False, index=True)
    to_number = Column(String(30), nullable=True)
    body = Column(Text, nullable=False)
    received_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
