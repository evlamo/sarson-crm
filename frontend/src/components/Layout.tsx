import { useState, useEffect, useCallback } from 'react';
import { Link, Outlet, useLocation, useNavigate } from '@tanstack/react-router';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import HelpWidget from './HelpWidget';
import KeyboardShortcutsModal from './KeyboardShortcutsModal';
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
  Clock,
  FileSpreadsheet,
  FileCode,
  GitBranch,
} from 'lucide-react';

const navItems = [
  { to: '/contacts', label: 'Contacts', icon: Users },
  { to: '/companies', label: 'Companies', icon: Building2 },
  { to: '/google-ads', label: 'Google Ads', icon: BarChart2 },
  { to: '/campaigns', label: 'Email Campaigns', icon: Mail },
  { to: '/sales-campaigns', label: 'Sales Campaigns', icon: Target },
  { to: '/campaign-stats', label: 'Campaign Stats', icon: BarChart3 },
  { to: '/lists', label: 'Lists', icon: Filter },
  { to: '/activity', label: 'Activity', icon: Clock },
  { to: '/tags', label: 'Tags', icon: Tag },
  { to: '/import', label: 'Import', icon: Upload },
  { to: '/imports', label: 'Import History', icon: History },
];

const adminItems = [
  { to: '/admin/users', label: 'Users', icon: Shield },
  { to: '/admin/invites', label: 'Team & Invites', icon: UserPlus },
  { to: '/api-controls', label: 'API Controls', icon: KeyRound },
  { to: '/sheets', label: 'Sheets Sync', icon: FileSpreadsheet },
  { to: '/admin/docs', label: 'API Docs', icon: FileCode },
  { to: '/admin/changelog', label: 'Changelog', icon: GitBranch },
];

export default function Layout() {
  const user = useAuth((s) => s.user);
  const isAdmin = useAuth((s) => s.isAdmin);
  const logout = useAuth((s) => s.logout);
  const location = useLocation();
  const navigate = useNavigate();
  
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const [isShortcutsOpen, setIsShortcutsOpen] = useState(false);
  const [gPressed, setGPressed] = useState(false);

  // Keyboard shortcuts handler
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    // Don't trigger shortcuts when typing in inputs
    const target = e.target as HTMLElement;
    const isInput = target.tagName === 'INPUT' || 
                    target.tagName === 'TEXTAREA' || 
                    target.isContentEditable;
    
    if (isInput && e.key !== 'Escape') return;

    // Handle escape
    if (e.key === 'Escape') {
      setIsHelpOpen(false);
      setIsShortcutsOpen(false);
      setGPressed(false);
      return;
    }

    // Handle ? key (requires Shift on US keyboards)
    // Ctrl+? or Cmd+? opens shortcuts modal
    // Plain ? toggles help panel
    if (e.key === '?') {
      e.preventDefault();
      if (e.ctrlKey || e.metaKey) {
        // Ctrl+? or Cmd+? for shortcuts modal
        setIsShortcutsOpen(true);
      } else {
        // Plain ? toggles help panel
        setIsHelpOpen(prev => !prev);
      }
      return;
    }

    // Handle / for search focus
    if (e.key === '/' && !e.shiftKey) {
      e.preventDefault();
      const searchInput = document.querySelector('input[type="search"], input[placeholder*="Search"]') as HTMLInputElement;
      if (searchInput) {
        searchInput.focus();
      }
      return;
    }

    // Handle G prefix for navigation
    if (e.key.toLowerCase() === 'g' && !gPressed && !e.ctrlKey && !e.metaKey) {
      setGPressed(true);
      setTimeout(() => setGPressed(false), 1000); // Reset after 1 second
      return;
    }

    if (gPressed) {
      setGPressed(false);
      switch (e.key.toLowerCase()) {
        case 'c':
          e.preventDefault();
          navigate({ to: '/contacts' });
          break;
        case 'l':
          e.preventDefault();
          navigate({ to: '/lists' });
          break;
        case 'a':
          e.preventDefault();
          navigate({ to: '/activity' });
          break;
        case 'o':
          e.preventDefault();
          navigate({ to: '/companies' });
          break;
        case 's':
          e.preventDefault();
          navigate({ to: '/sales-campaigns' });
          break;
      }
      return;
    }

    // Handle N for new contact
    if (e.key.toLowerCase() === 'n' && !e.ctrlKey && !e.metaKey) {
      if (location.pathname.startsWith('/contacts')) {
        // Trigger new contact modal/button if on contacts page
        const newButton = document.querySelector('[data-new-contact]') as HTMLButtonElement;
        if (newButton) {
          e.preventDefault();
          newButton.click();
        }
      }
      return;
    }
  }, [gPressed, navigate, location.pathname]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

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
        <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
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

      {/* Help Widget - mounted globally */}
      <HelpWidget isOpen={isHelpOpen} onOpenChange={setIsHelpOpen} />

      {/* Keyboard Shortcuts Modal */}
      <KeyboardShortcutsModal 
        isOpen={isShortcutsOpen} 
        onClose={() => setIsShortcutsOpen(false)} 
      />
    </div>
  );
}
