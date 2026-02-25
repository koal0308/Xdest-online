from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Comment(Base):
    __tablename__ = "comments"
    
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_read_by_owner = Column(Boolean, default=False)
    upvote_count = Column(Integer, default=0)
    downvote_count = Column(Integer, default=0)
    
    post = relationship("Post", back_populates="comments")
    author = relationship("User", back_populates="comments")
    votes = relationship("CommentVote", back_populates="comment", cascade="all, delete-orphan")


class CommentVote(Base):
    """Speichert wer welchen Comment up/downvoted hat"""
    __tablename__ = "comment_votes"
    
    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(Integer, ForeignKey("comments.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vote_type = Column(String(10), default="upvote")  # upvote oder downvote
    created_at = Column(DateTime, default=datetime.utcnow)
    
    comment = relationship("Comment", back_populates="votes")
    user = relationship("User", back_populates="comment_votes")
