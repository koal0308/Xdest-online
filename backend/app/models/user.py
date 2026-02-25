from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    email_visible = Column(Boolean, default=False)  # Email sichtbar auf Profil
    avatar = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    github = Column(String(255), nullable=True)
    twitter = Column(String(255), nullable=True)  # Twitter/X Profil
    linkedin = Column(String(255), nullable=True)  # LinkedIn Profil
    website = Column(String(255), nullable=True)  # Persönliche Website
    github_token = Column(String(500), nullable=True)  # GitHub OAuth Token für API Zugriff
    provider = Column(String(50), nullable=False)  # github, google
    provider_id = Column(String(255), nullable=False)
    role = Column(String(50), default="developer")  # developer (GitHub) oder tester (Google)
    terms_accepted_at = Column(DateTime, nullable=True)  # Wann AGBs akzeptiert wurden
    created_at = Column(DateTime, default=datetime.utcnow)
    
    projects = relationship("Project", back_populates="owner")
    posts = relationship("Post", back_populates="author")
    comments = relationship("Comment", back_populates="author")
    reported_issues = relationship("Issue", back_populates="reporter")
    issue_responses = relationship("IssueResponse", back_populates="author")
    issue_votes = relationship("IssueVote", back_populates="user")
    response_votes = relationship("ResponseVote", back_populates="user")
    post_votes = relationship("PostVote", back_populates="user")
    comment_votes = relationship("CommentVote", back_populates="user")
    
    # Star Ratings
    project_ratings = relationship("ProjectRating", back_populates="user")
    received_ratings = relationship("UserRating", foreign_keys="UserRating.rated_user_id", back_populates="rated_user")
    given_ratings = relationship("UserRating", foreign_keys="UserRating.rater_user_id", back_populates="rater")
    
    # Collective Messages
    messages = relationship("Message", back_populates="author")
    message_replies = relationship("MessageReply", back_populates="author")
    message_votes = relationship("MessageVote", back_populates="user")
    message_reply_votes = relationship("MessageReplyVote", back_populates="user")
    
    # Offer Redemptions
    offer_redemptions = relationship("OfferRedemption", back_populates="user")
