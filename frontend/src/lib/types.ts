export interface Contact {
  id: string;
  first_name: string | null;
  middle_name: string | null;
  last_name: string | null;
  full_name: string | null;
  email: string | null;
  email_domain: string | null;
  phone: string | null;
  title: string | null;
  company: string | null;
  company_name: string | null;
  company_id: string | null;
  profile_url: string | null;
  status: string;
  source: string | null;
  contacted: boolean;
  sarson_rep: string | null;
  sales_rep: string | null;
  assigned_to: string | null;
  next_step: string | null;
  follow_up_date: string | null;
  last_contacted_at: string | null;
  notes: string | null;
  tags: { id: string; name: string; color: string; category: string }[];
  created_at: string;
  updated_at: string;
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
