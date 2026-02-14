from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    project_url = Column(String(500), nullable=True)  # Link zur Live-Demo/Website
    github_url = Column(String(500), nullable=True)
    image = Column(String(500), nullable=True)
    tags = Column(String(500), nullable=True)  # comma separated
    google_analytics_id = Column(String(50), nullable=True)  # z.B. G-XXXXXXXXXX
    plausible_domain = Column(String(200), nullable=True)  # z.B. myproject.com
    plausible_api_key = Column(String(100), nullable=True)  # Plausible API Key für Stats
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    owner = relationship("User", back_populates="projects")
    posts = relationship("Post", back_populates="project", cascade="all, delete-orphan")
    issues = relationship("Issue", back_populates="project", cascade="all, delete-orphan")
    ratings = relationship("ProjectRating", back_populates="project", cascade="all, delete-orphan")
    offers = relationship("Offer", back_populates="project", cascade="all, delete-orphan")
