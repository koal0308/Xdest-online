from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from app.database import Base


class OfferRedemption(Base):
    """Tracks who claimed which offer coupon and whether they fulfilled their test obligation."""
    __tablename__ = "offer_redemptions"
    
    id = Column(Integer, primary_key=True, index=True)
    offer_id = Column(Integer, ForeignKey("offers.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)  # The project the offer belongs to
    
    # Timestamps
    claimed_at = Column(DateTime, default=datetime.utcnow)  # When the user claimed the coupon
    deadline = Column(DateTime, nullable=False)  # claimed_at + 7 days
    
    # Test obligation tracking
    fulfilled = Column(Boolean, default=False)  # Has the user written an issue/comment for this project?
    fulfilled_at = Column(DateTime, nullable=True)  # When the obligation was fulfilled
    
    # Karma penalty tracking
    karma_penalty_applied = Column(Boolean, default=False)  # Was the -1 karma penalty applied?
    karma_penalty_reversed = Column(Boolean, default=False)  # Was it reversed after late fulfillment?
    
    # Relationships
    offer = relationship("Offer", back_populates="redemptions")
    user = relationship("User", back_populates="offer_redemptions")
    project = relationship("Project")
    
    @property
    def is_overdue(self):
        """Check if the deadline has passed without fulfillment."""
        return not self.fulfilled and datetime.utcnow() > self.deadline
    
    @property
    def days_remaining(self):
        """Days remaining until deadline."""
        if self.fulfilled:
            return 0
        remaining = (self.deadline - datetime.utcnow()).days
        return max(0, remaining)
