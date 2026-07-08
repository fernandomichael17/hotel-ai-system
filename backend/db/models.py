import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime, Float, Integer, Text, ForeignKey, JSON, Date, Index, UniqueConstraint, Uuid
)
from sqlalchemy.orm import relationship, declarative_base
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class Hotel(Base):
    """Master data hotel dalam grup Metland"""
    __tablename__ = "hotels"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    slug = Column(String(50), unique=True, nullable=False)
    wa_number = Column(String(20), unique=True, nullable=True)
    waha_session = Column(String(50), unique=True, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    sessions = relationship("Session", back_populates="hotel")
    documents = relationship("Document", back_populates="hotel")
    booking_drafts = relationship("BookingDraft", back_populates="hotel")
    guest_stays = relationship("GuestStay", back_populates="hotel")
    complaint_tickets = relationship("ComplaintTicket", back_populates="hotel")
    amenities_requests = relationship("AmenitiesRequest", back_populates="hotel")
    policies = relationship("HotelPolicy", back_populates="hotel")
    notification_logs = relationship("NotificationLog", back_populates="hotel")
    intent_logs = relationship("IntentLog", back_populates="hotel")


class Session(Base):
    """Sesi percakapan per user per hotel"""
    __tablename__ = "sessions"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    hotel_id = Column(Uuid, ForeignKey("hotels.id"), nullable=False)
    user_identifier = Column(String(20), nullable=False)
    channel = Column(String(20), default="whatsapp")
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    # Relationships
    hotel = relationship("Hotel", back_populates="sessions")
    messages = relationship("ConversationMessage", back_populates="session")
    booking_drafts = relationship("BookingDraft", back_populates="session")
    complaint_tickets = relationship("ComplaintTicket", back_populates="session")
    amenities_requests = relationship("AmenitiesRequest", back_populates="session")
    intent_logs = relationship("IntentLog", back_populates="session")

    __table_args__ = (
        Index("idx_session_user_hotel", "user_identifier", "hotel_id"),
        Index("idx_session_status_expires", "status", "expires_at"),
    )


class ConversationMessage(Base):
    """Setiap pesan dalam sesi percakapan"""
    __tablename__ = "conversation_messages"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id = Column(Uuid, ForeignKey("sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    detected_intent = Column(String(50), nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("Session", back_populates="messages")

    __table_args__ = (
        Index("idx_message_session_created", "session_id", "created_at"),
    )


class Document(Base):
    """Chunk dokumen knowledge base per hotel yang sudah di-embed untuk RAG"""
    __tablename__ = "documents"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    hotel_id = Column(Uuid, ForeignKey("hotels.id"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(768), nullable=True)
    source_file = Column(String(200), nullable=True)
    chunk_index = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    hotel = relationship("Hotel", back_populates="documents")

    __table_args__ = (
        Index("idx_document_hotel_active", "hotel_id", "is_active"),
    )


class BookingDraft(Base):
    """Draft booking yang dikumpulkan bot sebelum diteruskan ke HMS/sales"""
    __tablename__ = "booking_drafts"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    hotel_id = Column(Uuid, ForeignKey("hotels.id"), nullable=False)
    session_id = Column(Uuid, ForeignKey("sessions.id"), nullable=False)
    guest_name = Column(String(100), nullable=True)
    wa_number = Column(String(20), nullable=True)
    check_in_date = Column(String(50), nullable=True)
    check_out_date = Column(String(50), nullable=True)
    room_type = Column(String(50), nullable=True)
    num_guests = Column(Integer, nullable=True)
    special_request = Column(Text, nullable=True)
    upsell_accepted = Column(JSON, nullable=True)
    status = Column(String(30), default="draft")
    hms_booking_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    hotel = relationship("Hotel", back_populates="booking_drafts")
    session = relationship("Session", back_populates="booking_drafts")

    __table_args__ = (
        Index("idx_booking_draft_hotel_status", "hotel_id", "status"),
        Index("idx_booking_draft_wa_hotel", "wa_number", "hotel_id"),
    )


class GuestStay(Base):
    """Track status check-in tamu untuk enriched session"""
    __tablename__ = "guest_stays"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    hotel_id = Column(Uuid, ForeignKey("hotels.id"), nullable=False)
    wa_number = Column(String(20), nullable=False)
    guest_name = Column(String(100), nullable=False)
    room_number = Column(String(20), nullable=True)
    check_in_date = Column(Date, nullable=True)
    check_out_date = Column(Date, nullable=True)
    booking_source = Column(String(30), default="chatbot")
    hms_booking_id = Column(String(100), nullable=True)
    status = Column(String(20), default="checked_in")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    hotel = relationship("Hotel", back_populates="guest_stays")
    complaint_tickets = relationship("ComplaintTicket", back_populates="guest_stay")
    amenities_requests = relationship("AmenitiesRequest", back_populates="guest_stay")

    __table_args__ = (
        Index("idx_guest_stay_wa_hotel_status", "wa_number", "hotel_id", "status"),
    )


class ComplaintTicket(Base):
    """Tiket keluhan yang dibuat bot, bisa disertai foto dari tamu"""
    __tablename__ = "complaint_tickets"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    hotel_id = Column(Uuid, ForeignKey("hotels.id"), nullable=False)
    session_id = Column(Uuid, ForeignKey("sessions.id"), nullable=False)
    guest_stay_id = Column(Uuid, ForeignKey("guest_stays.id"), nullable=True)
    guest_name = Column(String(100), nullable=True)
    room_number = Column(String(20), nullable=True)
    complaint_type = Column(String(50), nullable=True)
    description = Column(Text, nullable=False)
    photo_urls = Column(JSON, nullable=True)
    department = Column(String(50), nullable=True)
    status = Column(String(30), default="open")
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    hotel = relationship("Hotel", back_populates="complaint_tickets")
    session = relationship("Session", back_populates="complaint_tickets")
    guest_stay = relationship("GuestStay", back_populates="complaint_tickets")

    __table_args__ = (
        Index("idx_complaint_hotel_status", "hotel_id", "status"),
        Index("idx_complaint_dept_status", "department", "status"),
    )


class AmenitiesRequest(Base):
    """Request layanan kamar dari tamu yang sedang menginap"""
    __tablename__ = "amenities_requests"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    hotel_id = Column(Uuid, ForeignKey("hotels.id"), nullable=False)
    session_id = Column(Uuid, ForeignKey("sessions.id"), nullable=False)
    guest_stay_id = Column(Uuid, ForeignKey("guest_stays.id"), nullable=True)
    room_number = Column(String(20), nullable=True)
    request_items = Column(JSON, nullable=False)
    status = Column(String(30), default="pending")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    hotel = relationship("Hotel", back_populates="amenities_requests")
    session = relationship("Session", back_populates="amenities_requests")
    guest_stay = relationship("GuestStay", back_populates="amenities_requests")

    __table_args__ = (
        Index("idx_amenities_hotel_status", "hotel_id", "status"),
    )


class HotelPolicy(Base):
    """Policy per hotel yang disimpan sebagai JSON fleksibel"""
    __tablename__ = "hotel_policies"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    hotel_id = Column(Uuid, ForeignKey("hotels.id"), nullable=False)
    policy_type = Column(String(50), nullable=False)
    rules = Column(JSON, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    hotel = relationship("Hotel", back_populates="policies")

    __table_args__ = (
        UniqueConstraint("hotel_id", "policy_type", name="uq_hotel_policy_type"),
        Index("idx_hotel_policy_type_active", "hotel_id", "policy_type", "is_active"),
    )


class NotificationLog(Base):
    """Log semua notifikasi yang keluar dari sistem"""
    __tablename__ = "notification_logs"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    hotel_id = Column(Uuid, ForeignKey("hotels.id"), nullable=False)
    notification_type = Column(String(50), nullable=False)
    channel = Column(String(20), nullable=False)
    recipient = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String(20), default="sent")
    reference_id = Column(Uuid, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    hotel = relationship("Hotel", back_populates="notification_logs")

    __table_args__ = (
        Index("idx_notification_hotel_type", "hotel_id", "notification_type"),
        Index("idx_notification_reference", "reference_id"),
    )


class IntentLog(Base):
    """Log setiap klasifikasi intent oleh model"""
    __tablename__ = "intent_logs"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    hotel_id = Column(Uuid, ForeignKey("hotels.id"), nullable=True)
    session_id = Column(Uuid, ForeignKey("sessions.id"), nullable=True)
    message = Column(Text, nullable=False)
    detected_intent = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=False)
    latency_ms = Column(Integer, nullable=True)
    was_correct = Column(Boolean, nullable=True)
    correct_intent = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    hotel = relationship("Hotel", back_populates="intent_logs")
    session = relationship("Session", back_populates="intent_logs")

    __table_args__ = (
        Index("idx_intent_hotel_detected", "hotel_id", "detected_intent"),
        Index("idx_intent_created_at", "created_at"),
    )
