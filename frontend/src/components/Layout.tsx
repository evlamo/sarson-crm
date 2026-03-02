import { Link, Outlet, useLocation } from '@tanstack/react-router';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  Users,
  Building2,
  BarChart2,
  Mail,
  Filter,
  Upload,
  LogOut,
  Tag,
  History,
  Shield,
  BarChart3,
  UserPlus,
  KeyRound,
  Target,
} from 'lucide-react';

const navItems = [
  { to: '/contacts', label: 'Contacts', icon: Users },
  { to: '/companies', label: 'Companies', icon: Building2 },
  { to: '/google-ads', label: 'Google Ads', icon: BarChart2 },
  { to: '/campaigns', label: 'Email Campaigns', icon: Mail },
  { to: '/sales-campaigns', label: 'Sales Campaigns', icon: Target },
  { to: '/campaign-stats', label: 'Campaign Stats', icon: BarChart3 },
  { to: '/lists', label: 'Lists', icon: Filter },
  { to: '/tags', label: 'Tags', icon: Tag },
  { to: '/import', label: 'Import', icon: Upload },
  { to: '/imports', label: 'Import History', icon: History },
];

const adminItems = [
  { to: '/admin/users', label: 'Users', icon: Shield },
  { to: '/admin/invites', label: 'Team & Invites', icon: UserPlus },
  { to: '/api-controls', label: 'API Controls', icon: KeyRound },
];

export default function Layout() {
  const user = useAuth((s) => s.user);
  const isAdmin = useAuth((s) => s.isAdmin);
  const logout = useAuth((s) => s.logout);
  const location = useLocation();

  return (
    <div className="h-screen bg-background flex overflow-hidden">
      {/* Sidebar — Sarson Navy */}
      <aside className="w-56 bg-[#253a52] flex flex-col shrink-0 sticky top-0 h-screen">
        <div className="h-14 flex items-center gap-2.5 px-4 border-b border-white/10">
          <div className="w-7 h-7 rounded bg-white/15 flex items-center justify-center text-white text-xs font-bold shrink-0">
            SF
          </div>
          <Link to="/" className="font-semibold text-sm text-white tracking-tight leading-tight">
            Sarson Funds <span className="text-white/60 font-normal text-xs">CRM</span>
          </Link>
        </div>
        <nav className="flex-1 py-3 px-2 space-y-0.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.to || location.pathname.startsWith(item.to + '/');
            return (
              <Link
                key={item.to}
                to={item.to}
                className={cn(
                  'flex items-center gap-3 px-3 py-2 text-sm rounded-md transition-colors',
                  isActive
                    ? 'bg-[#2b5570] text-white'
                    : 'text-white/70 hover:text-white hover:bg-[#2b5570]/60'
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
          {isAdmin && (
            <>
              <div className="my-2 mx-3 border-t border-white/10" />
              <p className="px-3 py-1 text-xs font-semibold text-white/50 uppercase tracking-wider">Admin</p>
              {adminItems.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.to || location.pathname.startsWith(item.to + '/');
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2 text-sm rounded-md transition-colors',
                      isActive
                        ? 'bg-[#2b5570] text-white'
                        : 'text-white/70 hover:text-white hover:bg-[#2b5570]/60'
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </Link>
                );
              })}
            </>
          )}
        </nav>
        <div className="border-t border-white/10 p-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-white/60 truncate">{user?.name}</span>
            <Button variant="ghost" size="icon" className="h-8 w-8 text-white/60 hover:text-white hover:bg-white/10" onClick={logout} title="Sign Out">
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}
