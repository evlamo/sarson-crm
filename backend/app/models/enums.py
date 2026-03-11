from enum import Enum


class ContactStatus(str, Enum):
    POC = "poc"
    LEAD = "lead"
    CUSTOMER = "customer"
    PROSPECT = "prospect"
    INACTIVE = "inactive"


class InviteStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class CampaignStatus(str, Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    SENT = "sent"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    RESTRICTED = "restricted"
