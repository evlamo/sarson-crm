"""Data standardization engine for contact imports.

Handles: phone normalization, email cleanup, name casing, status mapping,
date parsing, boolean normalization, country normalization, CSV injection prevention.
"""

import re
from datetime import datetime, date
from typing import Dict, List, Optional

# ── CSV injection prevention ──
_FORMULA_CHARS = {"=", "+", "-", "@", "\t", "\r"}


def sanitize_value(value: str) -> str:
    """Strip CSV injection prefixes and whitespace."""
    v = value.strip()
    if v and v[0] in _FORMULA_CHARS:
        v = "'" + v
    return v


# ── Header mapping ──
HEADER_ALIASES: Dict[str, str] = {
    # first name
    "first": "first_name", "first name": "first_name", "firstname": "first_name",
    "first_name": "first_name", "given name": "first_name", "given_name": "first_name",
    # middle name
    "middle": "middle_name", "middle name": "middle_name", "middle_name": "middle_name",
    # last name
    "last": "last_name", "last name": "last_name", "lastname": "last_name",
    "last_name": "last_name", "surname": "last_name", "family name": "last_name",
    # email
    "email": "email", "email address": "email", "e-mail": "email",
    "email_address": "email", "e_mail": "email", "e-mail address": "email",
    # phone
    "phone": "phone", "phone number": "phone", "telephone": "phone",
    "mobile": "phone", "cell": "phone", "cell phone": "phone",
    "phone_number": "phone", "mobile phone": "phone", "telephone number": "phone",
    # title
    "title": "title", "job title": "title", "position": "title",
    "job_title": "title", "role": "title",
    # company
    "company": "company", "organization": "company", "org": "company",
    "company name": "company", "company_name": "company", "organisation": "company",
    "vc/company": "company",
    # location
    "city": "city", "state": "state", "province": "state",
    "country": "country", "region": "state",
    # status
    "status": "status", "lead status": "status",
    # source
    "source": "lead_source", "lead source": "lead_source", "lead_source": "lead_source",
    # sarson rep
    "sarson rep": "sarson_rep", "sf rep": "sarson_rep", "rep": "sarson_rep",
    "sarson_rep": "sarson_rep", "assigned": "sarson_rep",
    # next step
    "next step": "next_step", "next_step": "next_step", "nextstep": "next_step",
    # dates
    "last contacted": "last_contacted_at", "last contact": "last_contacted_at",
    "last_contacted_at": "last_contacted_at", "last contacted at": "last_contacted_at",
    # contacted
    "contacted": "contacted",
    # notes
    "notes": "notes", "note": "notes", "comment": "notes", "comments": "notes",
    # urls
    "linkedin": "linkedin_url", "linkedin url": "linkedin_url", "linkedin_url": "linkedin_url",
    "website": "website", "url": "website", "web": "website",
    "profile url": "profile_url", "profile_url": "profile_url", "contact url": "profile_url",
}


def map_headers(headers: List[str]) -> Dict[str, str]:
    """Map raw column headers to CRM field names.
    
    Returns: {original_header: crm_field_name}
    """
    mapping = {}
    for h in headers:
        norm = re.sub(r"\s+", " ", h.strip().lower()).rstrip("|").strip()
        # Direct match
        if norm in HEADER_ALIASES:
            mapping[h] = HEADER_ALIASES[norm]
        else:
            # Try underscore variant
            underscore = norm.replace(" ", "_")
            if underscore in HEADER_ALIASES:
                mapping[h] = HEADER_ALIASES[underscore]
    return mapping


# ── Status mapping ──
STATUS_MAP = {
    # Active
    "active": "active", "active client": "active", "client": "active",
    # Hot
    "hot": "hot", "hot lead": "hot",
    # Warm
    "warm": "warm", "warm lead": "warm",
    # Prospect
    "prospect": "prospect", "new": "prospect", "new lead": "prospect", "lead": "prospect",
    # Cold
    "cold": "cold", "cold lead": "cold",
    # POC
    "poc": "poc", "point of contact": "poc",
    # N/A
    "n/a": "na", "na": "na", "none": "na", "n.a.": "na",
    # Legacy mappings (keep for old data)
    "qualified": "prospect", "qualified lead": "prospect",
    "lost": "na", "dead": "na", "closed lost": "na",
    "won": "active", "closed won": "active",
    "inactive": "na", "churned": "na",
    "do not contact": "na", "dnc": "na",
}


def normalize_status(val: str) -> str:
    if not val:
        return "prospect"
    key = val.strip().lower()
    return STATUS_MAP.get(key, "prospect")


# ── Phone normalization ──
def normalize_phone(val: str) -> str:
    """Normalize phone to E.164 format (+1XXXXXXXXXX for US)."""
    if not val:
        return ""
    digits = re.sub(r"[^\d+]", "", val)
    # Strip leading + for processing
    has_plus = digits.startswith("+")
    raw_digits = digits.lstrip("+")
    
    if not raw_digits:
        return ""
    
    # If 10 digits, assume US
    if len(raw_digits) == 10:
        return f"+1{raw_digits}"
    # If 11 digits starting with 1, US
    if len(raw_digits) == 11 and raw_digits[0] == "1":
        return f"+{raw_digits}"
    # If already has country code format
    if has_plus and len(raw_digits) >= 10:
        return f"+{raw_digits}"
    # Otherwise return cleaned but not E.164
    return val.strip()


# ── Email normalization ──
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def normalize_email(val: str) -> str:
    if not val:
        return ""
    cleaned = val.strip().lower()
    if _EMAIL_RE.match(cleaned):
        return cleaned
    return ""  # invalid → empty


# ── Name normalization ──
def normalize_name(val: str) -> str:
    if not val:
        return ""
    v = val.strip()
    # Title case if ALL CAPS
    if v == v.upper() and len(v) > 1:
        v = v.title()
    return v


# ── Date normalization ──
_DATE_FORMATS = [
    "%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y",
    "%d/%m/%Y", "%Y/%m/%d", "%m.%d.%Y",
    "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y",
    "%d %B %Y", "%d %b %Y",
]


def normalize_date(val: str) -> Optional[datetime]:
    """Parse date string into datetime. Handles Excel serial dates too."""
    if not val or not val.strip():
        return None
    val = val.strip()
    
    # Excel serial date (number)
    try:
        serial = float(val)
        if 1 < serial < 100000:  # reasonable range
            from datetime import timedelta
            base = datetime(1899, 12, 30)
            return base + timedelta(days=serial)
    except (ValueError, TypeError):
        pass
    
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    
    # Last resort: dateutil
    try:
        from dateutil import parser as dateutil_parser
        return dateutil_parser.parse(val)
    except Exception:
        pass
    
    return None


# ── Boolean normalization ──
_TRUE_VALUES = {"yes", "true", "1", "x", "y", "on"}
_FALSE_VALUES = {"no", "false", "0", "n", "off", ""}


def normalize_bool(val: str) -> bool:
    if not val:
        return False
    return val.strip().lower() in _TRUE_VALUES


# ── Country normalization ──
COUNTRY_MAP = {
    "us": "US", "usa": "US", "united states": "US", "united states of america": "US",
    "u.s.": "US", "u.s.a.": "US", "america": "US",
    "uk": "GB", "united kingdom": "GB", "great britain": "GB", "england": "GB",
    "ca": "CA", "canada": "CA",
    "au": "AU", "australia": "AU",
}


def normalize_country(val: str) -> str:
    if not val:
        return "US"
    key = val.strip().lower()
    return COUNTRY_MAP.get(key, val.strip().upper()[:2] if len(val.strip()) == 2 else val.strip())


# ── Master normalizer ──
def normalize_row(raw: Dict[str, str]) -> Dict:
    """Normalize a mapped row dict. Keys should already be CRM field names."""
    result = {}
    
    for field, val in raw.items():
        if not isinstance(val, str):
            val = str(val) if val is not None else ""
        
        # Sanitize all values
        val = sanitize_value(val)
        
        if field == "email":
            result[field] = normalize_email(val)
        elif field == "phone":
            result[field] = normalize_phone(val)
        elif field in ("first_name", "middle_name", "last_name"):
            result[field] = normalize_name(val)
        elif field == "status":
            result[field] = normalize_status(val)
        elif field == "last_contacted_at":
            result[field] = normalize_date(val)
        elif field == "contacted":
            result[field] = normalize_bool(val)
        elif field == "country":
            result[field] = normalize_country(val)
        elif field == "lead_source":
            result[field] = val
        elif field in ("title", "company", "city", "state", "sarson_rep",
                       "next_step", "notes", "linkedin_url", "website", "profile_url"):
            result[field] = val
        # Skip unknown fields
    
    return result
