
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class ChatConversation(Base):
    __tablename__ = "chat_conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(150), nullable=False, default="New conversation")
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    messages = relationship(
        "ChatMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.id",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        Integer,
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    conversation = relationship(
        "ChatConversation",
        back_populates="messages",
    )
