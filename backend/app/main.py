from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.config import settings
from app.auth.router import router as auth_router, users_router
from app.routers.contacts import router as contacts_router
from app.routers.companies import router as companies_router
from app.routers.tags import router as tags_router
from app.routers.imports import router as imports_router
from app.routers.segments import router as segments_router
from app.routers.lists import router as lists_router
from app.routers.campaigns import router as campaigns_router
from app.routers.webhooks import router as webhooks_router
from app.routers.templates import router as templates_router
from app.routers.deals import router as deals_router
from app.routers.campaign_stats import router as campaign_stats_router
from app.routers.invites import router as invites_router
from app.routers.campaign_lists import router as campaign_lists_router
from app.routers.google_ads import router as google_ads_router
from app.routers.api_controls import router as api_controls_router
# Phase 2: Campaign Hierarchy + DNC
from app.routers.sales_campaigns import router as sales_campaigns_router
from app.routers.email_campaigns_hierarchy import router as email_campaigns_hierarchy_router
from app.routers.dnc import router as dnc_router
from app.models import google_ads as _google_ads_models  # noqa
from app.models import api_credentials as _api_credentials_models  # noqa

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Speranza CRM",
    description="Investment firm CRM - replaces Salesforce + Mailchimp",
    version="1.0.0",
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url="/redoc" if settings.environment == "development" else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# -- Security Headers Middleware --------------------------------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

app.add_middleware(SecurityHeadersMiddleware)

_origins = [settings.frontend_url]
if settings.environment == "development":
    _origins += ["http://localhost:3000", "http://localhost:5173", "http://192.168.0.41:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(contacts_router)
app.include_router(companies_router)
app.include_router(tags_router)
app.include_router(imports_router)
app.include_router(segments_router)
app.include_router(lists_router)
app.include_router(campaigns_router)
app.include_router(webhooks_router)
app.include_router(templates_router)
app.include_router(deals_router)
app.include_router(campaign_stats_router)
app.include_router(invites_router, prefix="/api/v1")
app.include_router(campaign_lists_router)
app.include_router(google_ads_router)
app.include_router(api_controls_router)
# Phase 2: Campaign Hierarchy + DNC
app.include_router(sales_campaigns_router)
app.include_router(email_campaigns_hierarchy_router)
app.include_router(dnc_router)

@app.get("/health")
def health():
    return {"status": "ok", "service": "Speranza CRM API"}
