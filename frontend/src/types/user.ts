export type UserRole = "admin" | "user" | "restricted";

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  avatar_url?: string;
  is_active: boolean;
  last_login?: string;
  created_at: string;
  updated_at: string;
}

export interface UserInvite {
  id: string;
  email: string;
  invited_by: string;
  status: "pending" | "accepted" | "revoked" | "expired";
  created_at: string;
  expires_at: string;
  accepted_at?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}
