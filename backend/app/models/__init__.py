from app.models.user import User
from app.models.company import Company
from app.models.contact import Contact
from app.models.tag import Tag, ContactTag
from app.models.deal import Deal, Pipeline, DealContact
from app.models.activity import Activity
from app.models.campaign import EmailCampaign, EmailSend, EmailTemplate
from app.models.segment import Segment
from app.models.import_job import ImportJob
from app.models.custom_field import CustomFieldDefinition
from app.models.static_list import StaticList, StaticListMember
from app.models.user_invite import UserInvite, InviteStatus

# ========== Phase 1 Foundation Models ==========
from app.models.sales_campaign import SalesCampaign, CampaignContact
from app.models.audit import AuditLog, ContactFieldHistory, DbSnapshot
from app.models.sheets import SheetsExport, SheetsImportReview

# ========== Phase 7 OAuth ==========
from app.models.oauth_state import OAuthState
