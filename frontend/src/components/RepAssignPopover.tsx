import { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Separator } from '@/components/ui/separator';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import { Check, Plus, X, Loader2, UserMinus } from 'lucide-react';
import api from '@/lib/api';

interface CrmUser {
  id: string;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
}

function getInitials(name: string): string {
  return name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

interface RepAssignPopoverProps {
  contactId: string;
  currentRep: string | null;
  /** Render a slightly larger trigger for detail pages */
  variant?: 'table' | 'detail';
}

export function RepAssignPopover({ contactId, currentRep, variant = 'table' }: RepAssignPopoverProps) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [customName, setCustomName] = useState('');
  const searchRef = useRef<HTMLInputElement>(null);

  const { data: users = [] } = useQuery<CrmUser[]>({
    queryKey: ['users'],
    queryFn: async () => {
      const res = await api.get('/users/');
      return res.data;
    },
    staleTime: 60_000,
    enabled: open,
  });

  const mutation = useMutation({
    mutationFn: async (value: string | null) => {
      await api.patch(`/contacts/${contactId}`, { sarson_rep: value });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
      queryClient.invalidateQueries({ queryKey: ['contact', contactId] });
      setOpen(false);
    },
    onError: () => {
      toast.error('Failed to update sales rep');
    },
  });

  useEffect(() => {
    if (open) {
      setSearch('');
      setCustomName('');
      setTimeout(() => searchRef.current?.focus(), 50);
    }
  }, [open]);

  const activeUsers = users.filter((u) => u.is_active);
  const filteredUsers = search.trim()
    ? activeUsers.filter(
        (u) =>
          u.name.toLowerCase().includes(search.toLowerCase()) ||
          u.email.toLowerCase().includes(search.toLowerCase())
      )
    : activeUsers;

  const handleSelectUser = (name: string) => {
    mutation.mutate(name);
  };

  const handleUnassign = () => {
    mutation.mutate(null);
  };

  const handleCustomSet = () => {
    const val = customName.trim();
    if (val) mutation.mutate(val);
  };

  const isTable = variant === 'table';

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          onClick={(e) => e.stopPropagation()}
          className={`inline-flex items-center gap-1.5 rounded-md transition-colors hover:bg-muted ${
            isTable
              ? 'px-1.5 py-0.5 text-sm -mx-1'
              : 'px-2 py-1 text-sm'
          } ${mutation.isPending ? 'opacity-60 pointer-events-none' : ''}`}
        >
          {mutation.isPending ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : currentRep ? (
            <span className="truncate max-w-[160px]">{currentRep}</span>
          ) : (
            <span className="text-muted-foreground italic flex items-center gap-1">
              <Plus className="h-3 w-3" />
              {isTable ? '—' : 'Assign rep'}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent
        className="w-[280px] p-0"
        align="start"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search */}
        <div className="p-2 pb-1">
          <Input
            ref={searchRef}
            placeholder="Search team..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-8 text-sm"
          />
        </div>

        {/* User list */}
        <div className="max-h-[200px] overflow-y-auto px-1 py-1">
          {filteredUsers.map((user) => {
            const isSelected = currentRep === user.name;
            return (
              <button
                key={user.id}
                onClick={() => handleSelectUser(user.name)}
                className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm hover:bg-muted transition-colors text-left"
              >
                <div className="h-7 w-7 rounded-full bg-[#1e3a5f] text-white flex items-center justify-center text-xs font-medium shrink-0">
                  {getInitials(user.name)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium truncate">{user.name}</div>
                  <div className="text-xs text-muted-foreground truncate">{user.email}</div>
                </div>
                {isSelected && <Check className="h-4 w-4 text-primary shrink-0" />}
              </button>
            );
          })}
          {filteredUsers.length === 0 && (
            <div className="text-xs text-muted-foreground text-center py-2">No users found</div>
          )}

          {/* Unassign */}
          {currentRep && (
            <button
              onClick={handleUnassign}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm hover:bg-muted transition-colors text-left text-muted-foreground"
            >
              <UserMinus className="h-4 w-4 shrink-0 ml-1.5" />
              <span>Unassign</span>
            </button>
          )}
        </div>

        <Separator />

        {/* Free text fallback */}
        <div className="p-2 space-y-1.5">
          <div className="text-xs text-muted-foreground">Or assign manually</div>
          <div className="flex items-center gap-1.5">
            <Input
              value={customName}
              onChange={(e) => setCustomName(e.target.value)}
              placeholder="Enter any name..."
              className="h-7 text-xs flex-1"
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleCustomSet();
              }}
            />
            <Button
              size="sm"
              variant="secondary"
              className="h-7 px-2 text-xs"
              onClick={handleCustomSet}
              disabled={!customName.trim()}
            >
              Set
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
