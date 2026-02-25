from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    upvote_count = Column(Integer, default=0)
    downvote_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    author = relationship("User", back_populates="messages")
    replies = relationship("MessageReply", back_populates="message", order_by="MessageReply.created_at")
    votes = relationship("MessageVote", back_populates="message", cascade="all, delete-orphan")

class MessageReply(Base):
    __tablename__ = "message_replies"
    
    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    upvote_count = Column(Integer, default=0)
    downvote_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    message = relationship("Message", back_populates="replies")
    author = relationship("User", back_populates="message_replies")
    votes = relationship("MessageReplyVote", back_populates="reply", cascade="all, delete-orphan")


class MessageVote(Base):
    """Up/Downvotes für Community Messages"""
    __tablename__ = "message_votes"
    
    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vote_type = Column(String(10), default="upvote")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    message = relationship("Message", back_populates="votes")
    user = relationship("User", back_populates="message_votes")


class MessageReplyVote(Base):
    """Up/Downvotes für Community Replies"""
    __tablename__ = "message_reply_votes"
    
    id = Column(Integer, primary_key=True, index=True)
    reply_id = Column(Integer, ForeignKey("message_replies.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vote_type = Column(String(10), default="upvote")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    reply = relationship("MessageReply", back_populates="votes")
    user = relationship("User", back_populates="message_reply_votes")
