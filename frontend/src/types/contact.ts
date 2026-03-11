export enum ContactStatusEnum {
  POC = "poc",
  LEAD = "lead",
  CUSTOMER = "customer",
  PROSPECT = "prospect",
  INACTIVE = "inactive",
}

export type ContactStatus = ContactStatusEnum | "poc" | "lead" | "customer" | "prospect" | "inactive";

export interface Tag {
  id: string;
  name: string;
  color?: string;
}

export interface Contact {
  id: string;
  first_name?: string;
  middle_name?: string;
  last_name: string;
  email?: string;
  email_secondary?: string;
  phone?: string;
  phone_secondary?: string;
  full_name: string;
  
  // Professional
  title?: string;
  company?: string;
  company_id?: string;
  department?: string;
  linkedin_url?: string;
  website?: string;
  sarson_rep?: string;
  sales_rep?: string;
  
  // Location
  city?: string;
  state?: string;
  country: string;
  timezone?: string;
  
  // CRM
  contact_type: string;
  status: ContactStatus;
  lead_source?: string;
  owner_id?: string;
  assigned_to?: string;
  next_step?: string;
  follow_up_date?: string;
  contacted: boolean;
  
  // Engagement
  contact_method_preference?: string;
  contact_method_custom?: string;
  last_contacted_at?: string;
  last_emailed_at?: string;
  email_open_count: number;
  email_click_count: number;
  
  // Email deliverability
  email_valid: boolean;
  email_bounced: boolean;
  email_unsubscribed: boolean;
  unsubscribed_at?: string;
  
  // Investment-specific
  commitment_amount?: number;
  commitment_currency: string;
  investor_tier?: string;
  fund_interest?: string[];
  accredited_status?: boolean;
  kyc_completed: boolean;
  kyc_completed_at?: string;
  
  // Google Ads
  gclid?: string;
  gclid_captured_at?: string;
  
  // Meta
  custom_fields?: Record<string, any>;
  notes?: string;
  tags: Tag[];
  
  created_at: string;
  updated_at: string;
  created_by?: string;
}

export interface ContactCreateRequest {
  first_name?: string;
  last_name: string;
  email?: string;
  phone?: string;
  company?: string;
  status?: ContactStatus;
  notes?: string;
  tags?: string[];
}

export interface ContactUpdateRequest extends Partial<ContactCreateRequest> {
  id: string;
}
