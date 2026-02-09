from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum

class IssueType(str, enum.Enum):
    BUG = "bug"              # Fehler/Bug
    FEATURE = "feature"      # Feature Request / Verbesserung
    QUESTION = "question"    # Frage
    SECURITY = "security"    # Sicherheitsproblem
    DOCS = "docs"            # Dokumentation

class IssueStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    WONT_FIX = "wont_fix"

class Issue(Base):
    __tablename__ = "issues"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)  # Kann NULL sein wenn Projekt gelöscht
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Kann NULL sein wenn User gelöscht
    
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=False)
    screenshot = Column(String(500), nullable=True)  # Screenshot URL
    issue_type = Column(String(50), default="bug")  # bug, feature, question, security, docs
    status = Column(String(50), default="open")     # open, in_progress, resolved, closed, wont_fix
    helpful_count = Column(Integer, default=0)  # Anzahl der "Hilfreich" Votes für das Issue (von dest)
    github_reactions = Column(Integer, default=0)  # Anzahl der 👍 Reactions von GitHub
    github_negative_reactions = Column(Integer, default=0)  # Anzahl der 👎 Reactions von GitHub
    
    # GitHub Sync
    github_issue_number = Column(Integer, nullable=True)  # GitHub Issue Nummer
    github_issue_url = Column(String(500), nullable=True)  # Link zum GitHub Issue
    
    # Referenz zur Quelle
    source_platform = Column(String(100), default="Xdest")  # Woher kommt das Issue
    
    # Notification tracking
    is_read_by_owner = Column(Boolean, default=False)  # Hat der Projekt-Owner das Issue gelesen?
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship("Project", back_populates="issues")
    reporter = relationship("User", back_populates="reported_issues")
    responses = relationship("IssueResponse", back_populates="issue", cascade="all, delete-orphan")
    votes = relationship("IssueVote", back_populates="issue", cascade="all, delete-orphan")

class IssueResponse(Base):
    __tablename__ = "issue_responses"
    
    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id"), nullable=True)  # Kann NULL sein wenn Issue gelöscht
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Kann NULL sein wenn User gelöscht
    
    content = Column(Text, nullable=False)
    helpful_count = Column(Integer, default=0)  # Anzahl der "Hilfreich" Votes
    is_solution = Column(Integer, default=0)  # 1 = vom Issue-Ersteller als Lösung markiert
    is_read_by_owner = Column(Boolean, default=False)  # Hat der Projekt-Owner die Antwort gelesen?
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    issue = relationship("Issue", back_populates="responses")
    author = relationship("User", back_populates="issue_responses")
    votes = relationship("ResponseVote", back_populates="response", cascade="all, delete-orphan")

class IssueVote(Base):
    """Speichert wer welches Issue als hilfreich markiert hat"""
    __tablename__ = "issue_votes"
    
    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    issue = relationship("Issue", back_populates="votes")
    user = relationship("User", back_populates="issue_votes")

class ResponseVote(Base):
    """Speichert wer welche Antwort als hilfreich markiert hat"""
    __tablename__ = "response_votes"
    
    id = Column(Integer, primary_key=True, index=True)
    response_id = Column(Integer, ForeignKey("issue_responses.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    response = relationship("IssueResponse", back_populates="votes")
    user = relationship("User", back_populates="response_votes")
