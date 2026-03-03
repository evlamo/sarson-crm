import { create } from "zustand";
import api from "@/lib/api";

interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  avatar_url?: string;
  is_restricted: boolean;
  auth_provider?: string;
}

interface GoogleOAuthStatus {
  enabled: boolean;
  login_url?: string;
}

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isAdmin: boolean;
  isRestricted: boolean;
  isRestricted: boolean;
  googleOAuthStatus: GoogleOAuthStatus | null;
  login: (email: string, password: string) => Promise<void>;
  loginWithToken: (token: string) => Promise<void>;
  logout: () => void;
  fetchUser: () => Promise<void>;
  checkGoogleOAuth: () => Promise<void>;
}

/**
 * Check if user has admin privileges (admin or owner role).
 */
function checkIsAdmin(role: string | undefined): boolean {
  return role === "admin" || role === "owner";
}

export const useAuth = create<AuthState>((set, get) => ({
  user: null,
  isLoading: true,
  isAuthenticated: false,
  isAdmin: false,
  isRestricted: false,
  googleOAuthStatus: null,

  login: async (email: string, password: string) => {
    const res = await api.post("/auth/login", { email, password });

    localStorage.setItem("access_token", res.data.access_token);
    if (res.data.refresh_token) {
      localStorage.setItem("refresh_token", res.data.refresh_token);
    }

    // Fetch user profile
    const userRes = await api.get("/auth/me");
    set({
      user: userRes.data,
      isAuthenticated: true,
      isLoading: false,
      isAdmin: checkIsAdmin(userRes.data.role),
      isRestricted: userRes.data.is_restricted ?? false,
    });
  },

  loginWithToken: async (token: string) => {
    localStorage.setItem("access_token", token);

    // Fetch user profile
    const userRes = await api.get("/auth/me");
    set({
      user: userRes.data,
      isAuthenticated: true,
      isLoading: false,
      isAdmin: checkIsAdmin(userRes.data.role),
      isRestricted: userRes.data.is_restricted ?? false,
    });
  },

  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    set({
      user: null,
      isAuthenticated: false,
      isAdmin: false,
      isRestricted: false,
    });
    window.location.href = "/login";
  },

  fetchUser: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      set({ isLoading: false, isAuthenticated: false, isAdmin: false, isRestricted: false });
      return;
    }
    try {
      const res = await api.get("/auth/me");
      set({
        user: res.data,
        isAuthenticated: true,
        isLoading: false,
        isAdmin: checkIsAdmin(res.data.role),
        isRestricted: res.data.is_restricted ?? false,
      });
    } catch {
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        isAdmin: false,
        isRestricted: false,
      });
    }
  },

  checkGoogleOAuth: async () => {
    try {
      const res = await api.get("/auth/google/status");
      set({ googleOAuthStatus: res.data });
    } catch {
      set({ googleOAuthStatus: { enabled: false } });
    }
  },
}));
