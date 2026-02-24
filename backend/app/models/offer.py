from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum

class OfferType(str, enum.Enum):
    FREE_TRIAL = "free_trial"           # z.B. "3 Monate kostenlos"
    DISCOUNT = "discount"               # z.B. "50% Rabatt"
    EARLY_ADOPTER = "early_adopter"     # z.B. "Early Adopter Preis"
    LIFETIME = "lifetime"               # z.B. "Lifetime Deal"
    BETA_ACCESS = "beta_access"         # z.B. "Kostenloser Beta-Zugang"
    OTHER = "other"

class Offer(Base):
    __tablename__ = "offers"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    
    title = Column(String(200), nullable=False)  # z.B. "Early Adopter Special"
    description = Column(Text, nullable=False)   # Detaillierte Beschreibung
    offer_type = Column(String(50), default="other")  # free_trial, discount, etc.
    
    # Offer Details
    original_price = Column(String(50), nullable=True)   # z.B. "29€/Monat"
    offer_price = Column(String(50), nullable=True)      # z.B. "Kostenlos" oder "14€/Monat"
    discount_percent = Column(Integer, nullable=True)    # z.B. 50 für 50%
    duration = Column(String(100), nullable=True)        # z.B. "3 Monate" oder "Lifetime"
    
    # Coupon/Code
    coupon_code = Column(String(50), nullable=True)      # z.B. "EARLY2026"
    redemption_url = Column(String(500), nullable=True)  # Link zum Einlösen
    
    # Limits
    max_redemptions = Column(Integer, nullable=True)     # Max. Anzahl Einlösungen (None = unbegrenzt)
    current_redemptions = Column(Integer, default=0)     # Aktuelle Einlösungen
    
    # Validity
    valid_from = Column(DateTime, default=datetime.utcnow)
    valid_until = Column(DateTime, nullable=True)        # None = kein Ablaufdatum
    is_active = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship("Project", back_populates="offers")
    redemptions = relationship("OfferRedemption", back_populates="offer", cascade="all, delete-orphan")
    
    @property
    def is_valid(self):
        """Check if offer is currently valid"""
        now = datetime.utcnow()
        if not self.is_active:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if self.max_redemptions and self.current_redemptions >= self.max_redemptions:
            return False
        return True
    
    @property
    def spots_left(self):
        """Return spots left or None if unlimited"""
        if self.max_redemptions:
            return max(0, self.max_redemptions - self.current_redemptions)
        return None
