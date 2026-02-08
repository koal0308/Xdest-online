from sqlalchemy import Column, Integer, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class ProjectRating(Base):
    """Sterne-Bewertung für Projekte (1-5 Sterne)"""
    __tablename__ = "project_ratings"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Wer bewertet
    stars = Column(Integer, nullable=False)  # 1-5 Sterne
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint: Ein User kann ein Projekt nur einmal bewerten
    __table_args__ = (
        UniqueConstraint('project_id', 'user_id', name='unique_project_rating'),
    )
    
    # Relationships
    project = relationship("Project", back_populates="ratings")
    user = relationship("User", back_populates="project_ratings")


class UserRating(Base):
    """Sterne-Bewertung für User (1-5 Sterne)"""
    __tablename__ = "user_ratings"
    
    id = Column(Integer, primary_key=True, index=True)
    rated_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Wer wird bewertet
    rater_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Wer bewertet
    stars = Column(Integer, nullable=False)  # 1-5 Sterne
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint: Ein User kann einen anderen User nur einmal bewerten
    __table_args__ = (
        UniqueConstraint('rated_user_id', 'rater_user_id', name='unique_user_rating'),
    )
    
    # Relationships
    rated_user = relationship("User", foreign_keys=[rated_user_id], back_populates="received_ratings")
    rater = relationship("User", foreign_keys=[rater_user_id], back_populates="given_ratings")
