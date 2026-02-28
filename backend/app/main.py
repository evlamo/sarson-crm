from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

app = FastAPI(
    title="Speranza CRM",
    description="Investment firm CRM — replaces Salesforce + Mailchimp",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

_origins = [settings.frontend_url]
if settings.environment == "development":
    _origins += ["http://localhost:3000", "http://localhost:5173", "http://192.168.0.41:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

@app.get("/health")
def health():
    return {"status": "ok", "service": "Speranza CRM API"}
