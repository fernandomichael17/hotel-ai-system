from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey, Date, Float, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
import uuid
from datetime import datetime, UTC
from .database import Base

def utcnow():
    return datetime.now(UTC)

class Hotel(Base):
    """Hotel configuration and details."""
    __tablename__ = "hotels"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    wa_number = Column(String, unique=True, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    
    sessions = relationship("Session", back_populates="hotel")
    documents = relationship("Document", back_populates="hotel")
    booking_drafts = relationship("BookingDraft", back_populates="hotel")
    complaint_tickets = relationship("ComplaintTicket", back_populates="hotel")
    guest_stays = relationship("GuestStay", back_populates="hotel")
    policies = relationship("HotelPolicy", back_populates="hotel")

class Session(Base):
    """User conversation session."""
    __tablename__ = "sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hotel_id = Column(UUID(as_uuid=True), ForeignKey("hotels.id"), index=True)
    user_identifier = Column(String, nullable=False)
    channel = Column(String, default="whatsapp")
    status = Column(String, default="active")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    expires_at = Column(DateTime, nullable=True)
    
    hotel = relationship("Hotel", back_populates="sessions")
    messages = relationship("ConversationMessage", back_populates="session")
    booking_drafts = relationship("BookingDraft", back_populates="session")
    complaint_tickets = relationship("ComplaintTicket", back_populates="session")

class ConversationMessage(Base):
    """Message within a session."""
    __tablename__ = "conversation_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), index=True)
    role = Column(String, nullable=False) # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    detected_intent = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    
    session = relationship("Session", back_populates="messages")

class Document(Base):
    """Knowledge base document for RAG."""
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hotel_id = Column(UUID(as_uuid=True), ForeignKey("hotels.id"), index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(768))
    source_file = Column(String, nullable=True)
    chunk_index = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    
    hotel = relationship("Hotel", back_populates="documents")

class BookingDraft(Base):
    """In-progress booking."""
    __tablename__ = "booking_drafts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hotel_id = Column(UUID(as_uuid=True), ForeignKey("hotels.id"), index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"))
    guest_name = Column(String, nullable=True)
    check_in_date = Column(String, nullable=True)
    check_out_date = Column(String, nullable=True)
    room_type = Column(String, nullable=True)
    num_guests = Column(Integer, nullable=True)
    status = Column(String, default="draft")
    created_at = Column(DateTime, default=utcnow)
    
    hotel = relationship("Hotel", back_populates="booking_drafts")
    session = relationship("Session", back_populates="booking_drafts")

class ComplaintTicket(Base):
    """Guest complaint ticket."""
    __tablename__ = "complaint_tickets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hotel_id = Column(UUID(as_uuid=True), ForeignKey("hotels.id"), index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"))
    guest_name = Column(String, nullable=True)
    room_number = Column(String, nullable=True)
    complaint_type = Column(String, nullable=True)
    description = Column(Text, nullable=False)
    department = Column(String, nullable=True)
    status = Column(String, default="open")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    
    hotel = relationship("Hotel", back_populates="complaint_tickets")
    session = relationship("Session", back_populates="complaint_tickets")

class GuestStay(Base):
    """Information about a guest's stay."""
    __tablename__ = "guest_stays"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hotel_id = Column(UUID(as_uuid=True), ForeignKey("hotels.id"), index=True)
    wa_number = Column(String, nullable=False)
    guest_name = Column(String, nullable=False)
    room_number = Column(String, nullable=False)
    check_in_date = Column(Date, nullable=False)
    check_out_date = Column(Date, nullable=False)
    booking_source = Column(String, nullable=False)
    status = Column(String, default="checked_in")
    created_at = Column(DateTime, default=utcnow)
    
    hotel = relationship("Hotel", back_populates="guest_stays")

class HotelPolicy(Base):
    """Hotel specific policies."""
    __tablename__ = "hotel_policies"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hotel_id = Column(UUID(as_uuid=True), ForeignKey("hotels.id"), index=True)
    policy_type = Column(String, nullable=False)
    rules = Column(JSON, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    
    hotel = relationship("Hotel", back_populates="policies")
