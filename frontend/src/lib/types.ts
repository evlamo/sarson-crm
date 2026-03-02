export interface Contact {
  id: string;
  first_name: string | null;
  middle_name: string | null;
  last_name: string | null;
  full_name: string;           // never null - defaults to ""
  email: string | null;
  email_domain: string | null;
  email_secondary: string | null;
  phone: string | null;
  phone_secondary: string | null;
  title: string | null;
  company: string | null;
  company_name: string | null;
  company_id: string | null;
  department: string | null;
  linkedin_url: string | null;
  website: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  timezone: string | null;
  status: string;
  source: string | null;       // maps to lead_source on backend
  contacted: boolean;
  sarson_rep: string | null;
  assigned_to: string | null;
  next_step: string | null;
  last_contacted_at: string | null;
  last_emailed_at: string | null;
  email_open_count: number;
  email_click_count: number;
  email_valid: boolean;
  email_bounced: boolean;
  email_unsubscribed: boolean;
  // DNC fields (Phase 2)
  master_dnc: boolean;
  master_dnc_reason: string | null;
  master_dnc_set_at: string | null;
  notes: string | null;
  custom_fields: Record<string, unknown>;
  tags: { id: string; name: string; color: string; category: string }[];
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  per_page: number;
}

export interface Campaign {
  id: string;
  name: string;
  subject: string;
  status: string;
  recipient_count: number;
  sent_count: number;
  open_count: number;
  click_count: number;
  created_at: string;
  sent_at: string | null;
}

export interface Company {
  id: string;
  name: string;
  domain: string | null;
  industry: string | null;
  company_type: string | null;
  website: string | null;
  linkedin_url: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  employee_count: number | null;
  revenue_range: string | null;
  description: string | null;
  notes: string | null;
  poc_contact_id: string | null;
  custom_fields: Record<string, unknown>;
  contact_count: number;
  owner_id: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface Deal {
  id: string;
  title: string;
  stage: string;
  amount: number | null;
  company_id: string | null;
  owner_id: string | null;
  created_at: string;
}

// Sales Campaign types (Phase 2)
export interface SalesCampaign {
  id: string;
  name: string;
  description: string | null;
  status: string;
  owner_id: string | null;
  contact_count: number;
  email_campaign_count: number;
  created_at: string;
  updated_at: string;
}

export interface CampaignContact {
  id: string;
  contact_id: string;
  contact_name: string;
  contact_email: string | null;
  contact_company: string | null;
  status: string;
  completion_status: string | null;
  excluded_reason: string | null;
  master_dnc: boolean;
  added_at: string;
  updated_at: string;
}
