import { Link, Outlet, useLocation } from '@tanstack/react-router';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  Users,
  Building2,
  Kanban,
  Mail,
  Filter,
  Upload,
  LogOut,
  Tag,
  History,
  Shield,
  BarChart3,
  UserPlus,
} from 'lucide-react';

const navItems = [
  { to: '/contacts', label: 'Contacts', icon: Users },
  { to: '/companies', label: 'Companies', icon: Building2 },
  { to: '/pipeline', label: 'Pipeline', icon: Kanban },
  { to: '/campaigns', label: 'Campaigns', icon: Mail },
  { to: '/campaign-stats', label: 'Campaign Stats', icon: BarChart3 },
  { to: '/segments', label: 'Segments', icon: Filter },
  { to: '/tags', label: 'Tags', icon: Tag },
  { to: '/import', label: 'Import', icon: Upload },
  { to: '/imports', label: 'Import History', icon: History },
];

const adminItems = [
  { to: '/admin/users', label: 'Users', icon: Shield },
  { to: '/admin/invites', label: 'Team & Invites', icon: UserPlus },
];

export default function Layout() {
  const user = useAuth((s) => s.user);
  const isAdmin = useAuth((s) => s.isAdmin);
  const logout = useAuth((s) => s.logout);
  const location = useLocation();

  return (
    <div className="min-h-screen bg-background flex">
      {/* Sidebar */}
      <aside className="w-56 border-r bg-card flex flex-col shrink-0">
        <div className="h-14 flex items-center px-4 border-b">
          <Link to="/" className="font-bold text-lg tracking-tight">
            Sarson Funds <span className="text-muted-foreground font-normal text-sm">CRM</span>
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
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
          {isAdmin && (
            <>
              <div className="my-2 mx-3 border-t" />
              <p className="px-3 py-1 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Admin</p>
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
                        ? 'bg-primary text-primary-foreground'
                        : 'text-muted-foreground hover:text-foreground hover:bg-muted'
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
        <div className="border-t p-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground truncate">{user?.name}</span>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={logout} title="Sign Out">
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
