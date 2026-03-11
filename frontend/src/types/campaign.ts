export enum CampaignStatusEnum {
  DRAFT = "draft",
  SCHEDULED = "scheduled",
  SENDING = "sending",
  SENT = "sent",
  PAUSED = "paused",
  CANCELLED = "cancelled",
}

export type CampaignStatus = CampaignStatusEnum | "draft" | "scheduled" | "sending" | "sent" | "paused" | "cancelled";

export interface Campaign {
  id: string;
  name: string;
  subject: string;
  preview_text?: string;
  body_html: string;
  body_text?: string;
  status: CampaignStatus;
  recipient_count: number;
  from_name: string;
  from_email: string;
  reply_to?: string;
  scheduled_at?: string;
  sent_at?: string;
  
  // Stats
  sent_count: number;
  delivered_count: number;
  open_count: number;
  unique_opens: number;
  click_count: number;
  unique_clicks: number;
  bounce_count: number;
  unsubscribe_count: number;
  spam_count: number;
  
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface EmailTemplate {
  id: string;
  name: string;
  subject: string;
  body_html: string;
  body_text?: string;
  category?: string;
  thumbnail?: string;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

export interface EmailSend {
  id: string;
  campaign_id: string;
  contact_id: string;
  email_address: string;
  message_id?: string;
  status: string;
  delivered_at?: string;
  first_opened_at?: string;
  last_opened_at?: string;
  open_count: number;
  first_clicked_at?: string;
  click_count: number;
  bounced_at?: string;
  bounce_type?: string;
  unsubscribed_at?: string;
  created_at: string;
}
