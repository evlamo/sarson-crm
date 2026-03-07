import { create } from 'zustand';
import api from '@/lib/api';

interface User {
  id: string;
  email: string;
  name: string;
  role: string;
}

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isAdmin: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  fetchUser: () => Promise<void>;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  isLoading: true,
  isAuthenticated: false,
  isAdmin: false,

  login: async (email: string, password: string) => {
    const res = await api.post('/auth/login', { email, password });

    localStorage.setItem('access_token', res.data.access_token);
    if (res.data.refresh_token) {
      localStorage.setItem('refresh_token', res.data.refresh_token);
    }

    // Fetch user profile
    const userRes = await api.get('/auth/me');
    set({ user: userRes.data, isAuthenticated: true, isLoading: false, isAdmin: userRes.data.role === 'admin' });
  },

  logout: () => {
    // Clear all auth-related storage
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    
    // Clear user session state
    set({ user: null, isAuthenticated: false, isAdmin: false });
    
    // Redirect to login with logout message
    window.location.href = '/login?logged_out=true';
  },

  fetchUser: async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      set({ isLoading: false, isAuthenticated: false });
      return;
    }
    try {
      const res = await api.get('/auth/me');
      set({ user: res.data, isAuthenticated: true, isLoading: false, isAdmin: res.data.role === 'admin' });
    } catch {
      set({ user: null, isAuthenticated: false, isLoading: false, isAdmin: false });
    }
  },
}));
