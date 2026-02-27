export interface Contact {
  id: string;
  first_name: string | null;
  middle_name: string | null;
  last_name: string | null;
  full_name: string;           // never null — defaults to ""
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
  profile_url: string | null;
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

export interface Deal {
  id: string;
  title: string;
  stage: string;
  amount: number | null;
  company_id: string | null;
  owner_id: string | null;
  created_at: string;
}
