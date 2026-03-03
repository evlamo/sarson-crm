import { useAuth } from "@/hooks/useAuth";
import { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from '@tanstack/react-router';
import { toast } from 'sonner';
import api from '@/lib/api';
import { formatDate } from '@/lib/formatDate';
import { getStatus } from '@/lib/statuses';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Separator } from '@/components/ui/separator';
import { Search, X, ExternalLink, UserPlus, Users, ChevronLeft, ChevronRight } from 'lucide-react';

// ── Types ─────────────────────────────────────────────────────────────────

interface CampaignList {
  id: string;
  name: string;
  description: string | null;
  filters: {
    statuses?: string[];
    tag_ids?: string[];
    company_ids?: string[];
  };
  contact_ids: string[];
  mc_segment_id: number | null;
  mc_synced_at: string | null;
  member_count: number;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

interface Tag {
  id: string;
  name: string;
  contact_count?: number;
}

interface ListMember {
  id: string;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  company: string | null;
  status: string | null;
  source: 'filter' | 'manual';
}

interface MembersPage {
  data: ListMember[];
  total: number;
  page: number;
  per_page: number;
}

// ── Constants ─────────────────────────────────────────────────────────────

const ALL_STATUSES = ['hot', 'warm', 'prospect', 'cold', 'poc', 'active', 'na'];

// ── Helpers ───────────────────────────────────────────────────────────────

function StatusPill({ status }: { status: string | null }) {
  if (!status) return <span className="text-muted-foreground text-xs">—</span>;
  const { label, badge } = getStatus(status);
  return (
    <span className={`inline-flex items-center text-xs font-medium px-2 py-0.5 rounded-full border ${badge}`}>
      {label}
    </span>
  );
}

function SyncStatusBadge({ list }: { list: CampaignList }) {
  if (!list.mc_synced_at) {
    return <Badge variant="outline" className="text-gray-500 border-gray-300">Not synced</Badge>;
  }
  const syncedAt = new Date(list.mc_synced_at).getTime();
  const updatedAt = new Date(list.updated_at).getTime();
  if (updatedAt > syncedAt + 1000) {
    return <Badge className="bg-yellow-100 text-yellow-700 border-yellow-300">Out of sync</Badge>;
  }
  const ago = Date.now() - syncedAt;
  const minutes = Math.floor(ago / 60000);
  const hours = Math.floor(ago / 3600000);
  const days = Math.floor(ago / 86400000);
  const timeStr = days > 0 ? `${days}d ago` : hours > 0 ? `${hours}h ago` : `${minutes}m ago`;
  return <Badge className="bg-green-100 text-green-700 border-green-300">Synced • {timeStr}</Badge>;
}

// ── Members Drawer ────────────────────────────────────────────────────────

function ListMembersDrawer({
  list,
  onClose,
  onMembersChanged,
}: {
  list: CampaignList;
  onClose: () => void;
  onMembersChanged: () => void;
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [page, setPage] = useState(1);
  const [addSearch, setAddSearch] = useState('');
  const [debouncedAddSearch, setDebouncedAddSearch] = useState('');
  const [showAddPanel, setShowAddPanel] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [addingId, setAddingId] = useState<string | null>(null);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const addTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const PER_PAGE = 50;

  // Debounce main search
  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => { setDebouncedSearch(search); setPage(1); }, 350);
    return () => { if (searchTimer.current) clearTimeout(searchTimer.current); };
  }, [search]);

  // Debounce add search
  useEffect(() => {
    if (addTimer.current) clearTimeout(addTimer.current);
    addTimer.current = setTimeout(() => setDebouncedAddSearch(addSearch), 350);
    return () => { if (addTimer.current) clearTimeout(addTimer.current); };
  }, [addSearch]);

  // Fetch members (paginated, searched)
  const { data: membersData, isLoading: membersLoading, refetch: refetchMembers } = useQuery<MembersPage>({
    queryKey: ['list-members', list.id, debouncedSearch, page],
    queryFn: async () => {
      const res = await api.get(`/campaign-lists/${list.id}/members`, {
        params: { search: debouncedSearch, page, per_page: PER_PAGE },
      });
      return res.data;
    },
    staleTime: 0,
  });

  // Search contacts to add
  const { data: addResults = [] } = useQuery<ListMember[]>({
    queryKey: ['contact-add-search', debouncedAddSearch],
    queryFn: async () => {
      if (!debouncedAddSearch || debouncedAddSearch.length < 2) return [];
      const res = await api.get('/contacts', { params: { search: debouncedAddSearch, per_page: 20 } });
      return (res.data.data || []).map((c: Record<string, unknown>) => ({
        id: c.id,
        first_name: c.first_name,
        last_name: c.last_name,
        email: c.email,
        company: c.company_name || c.company,
        status: c.status,
        source: 'filter' as const,
      }));
    },
    enabled: debouncedAddSearch.length >= 2,
  });

  const currentMemberIds = new Set(membersData?.data.map(m => m.id) ?? []);

  const patchList = async (newContactIds: string[]) => {
    await api.patch(`/campaign-lists/${list.id}`, { contact_ids: newContactIds });
    queryClient.invalidateQueries({ queryKey: ['campaign-lists'] });
    refetchMembers();
    onMembersChanged();
  };

  const removeContact = async (memberId: string) => {
    setRemovingId(memberId);
    try {
      const newIds = (list.contact_ids || []).filter(id => id !== memberId);
      await patchList(newIds);
      toast.success('Contact removed from list');
    } catch {
      toast.error('Failed to remove contact');
    } finally {
      setRemovingId(null);
    }
  };

  const addContact = async (contactId: string) => {
    setAddingId(contactId);
    try {
      const newIds = [...new Set([...(list.contact_ids || []), contactId])];
      await patchList(newIds);
      toast.success('Contact added to list');
      setAddSearch('');
    } catch {
      toast.error('Failed to add contact');
    } finally {
      setAddingId(null);
    }
  };

  const members = membersData?.data ?? [];
  const total = membersData?.total ?? 0;
  const totalPages = Math.ceil(total / PER_PAGE);
  const manualCount = members.filter(m => m.source === 'manual').length;
  const filterCount = members.filter(m => m.source === 'filter').length;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 z-40 transition-opacity"
        onClick={onClose}
      />

      {/* Drawer */}
      <div className="fixed right-0 top-0 h-full w-full max-w-2xl bg-background border-l shadow-2xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-start justify-between px-6 py-5 border-b shrink-0">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4 text-muted-foreground shrink-0" />
              <h2 className="text-lg font-semibold truncate">{list.name}</h2>
            </div>
            {list.description && (
              <p className="text-sm text-muted-foreground mt-0.5 truncate">{list.description}</p>
            )}
            <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
              <span><strong className="text-foreground">{total.toLocaleString()}</strong> total</span>
              {filterCount > 0 && <span>{filterCount.toLocaleString()} via filters</span>}
              {manualCount > 0 && <span>{manualCount.toLocaleString()} manual</span>}
            </div>
          </div>
          <button
            onClick={onClose}
            className="ml-4 p-1.5 rounded-md hover:bg-muted transition-colors shrink-0"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Toolbar */}
        <div className="px-6 py-3 border-b shrink-0 space-y-3">
          {/* Search existing members */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
            <Input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search members by name, email, or company..."
              className="pl-9 h-8 text-sm"
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          {/* Add contact toggle */}
          <button
            onClick={() => setShowAddPanel(v => !v)}
            className="flex items-center gap-1.5 text-sm text-[#253a52] font-medium hover:underline"
          >
            <UserPlus className="h-3.5 w-3.5" />
            {showAddPanel ? 'Hide add panel' : 'Add contact manually'}
          </button>

          {/* Add contact panel */}
          {showAddPanel && (
            <div className="border rounded-lg p-3 bg-muted/30 space-y-2">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
                <Input
                  value={addSearch}
                  onChange={e => setAddSearch(e.target.value)}
                  placeholder="Search contacts to add..."
                  className="pl-9 h-8 text-sm"
                  autoFocus
                />
              </div>
              {addResults.length > 0 && (
                <div className="divide-y border rounded-lg bg-background max-h-48 overflow-y-auto">
                  {addResults.map(c => {
                    const alreadyIn = currentMemberIds.has(c.id);
                    const name = [c.first_name, c.last_name].filter(Boolean).join(' ') || '—';
                    return (
                      <div key={c.id} className="flex items-center gap-3 px-3 py-2">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{name}</p>
                          <p className="text-xs text-muted-foreground truncate">{c.email}</p>
                        </div>
                        {alreadyIn ? (
                          <span className="text-xs text-muted-foreground px-2 py-1 rounded bg-muted">In list</span>
                        ) : (
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 text-xs"
                            disabled={addingId === c.id}
                            onClick={() => addContact(c.id)}
                          >
                            {addingId === c.id ? '...' : '+ Add'}
                          </Button>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
              {debouncedAddSearch.length >= 2 && addResults.length === 0 && (
                <p className="text-xs text-muted-foreground text-center py-2">No contacts found</p>
              )}
            </div>
          )}
        </div>

        {/* Members list */}
        <div className="flex-1 overflow-y-auto">
          {membersLoading ? (
            <div className="p-6 space-y-3">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="flex gap-3 animate-pulse">
                  <div className="h-8 w-8 rounded-full bg-muted shrink-0" />
                  <div className="flex-1 space-y-1.5 py-1">
                    <div className="h-3 bg-muted rounded w-1/3" />
                    <div className="h-2.5 bg-muted rounded w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          ) : members.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-center p-6">
              <Users className="h-8 w-8 text-muted-foreground/40 mb-2" />
              <p className="text-sm text-muted-foreground">
                {search ? 'No members match your search' : 'No members in this list'}
              </p>
            </div>
          ) : (
            <div className="divide-y">
              {members.map(member => {
                const name = [member.first_name, member.last_name].filter(Boolean).join(' ') || '—';
                const initials = ((member.first_name?.[0] ?? '') + (member.last_name?.[0] ?? '')).toUpperCase() || member.email?.[0]?.toUpperCase() || '?';
                const isManual = member.source === 'manual';

                return (
                  <div
                    key={member.id}
                    className="flex items-center gap-3 px-6 py-3 hover:bg-muted/40 group transition-colors"
                  >
                    {/* Avatar */}
                    <div className="h-8 w-8 rounded-full bg-[#1e293b] text-white flex items-center justify-center text-xs font-bold shrink-0">
                      {initials}
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <button
                          onClick={() => navigate({ to: '/contacts/$contactId', params: { contactId: member.id } })}
                          className="text-sm font-medium hover:text-[#253a52] hover:underline transition-colors text-left"
                        >
                          {name}
                        </button>
                        <span className={`inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded font-medium ${
                          isManual
                            ? 'bg-purple-50 text-purple-700 border border-purple-200'
                            : 'bg-blue-50 text-blue-700 border border-blue-200'
                        }`}>
                          {isManual ? '✦ manual' : '⊛ filter'}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                        {member.email && (
                          <span className="text-xs text-muted-foreground truncate max-w-[180px]">{member.email}</span>
                        )}
                        {member.company && (
                          <>
                            <span className="text-muted-foreground/40 text-xs">·</span>
                            <span className="text-xs text-muted-foreground truncate max-w-[120px]">{member.company}</span>
                          </>
                        )}
                      </div>
                    </div>

                    {/* Status + actions */}
                    <div className="flex items-center gap-2 shrink-0">
                      <StatusPill status={member.status} />
                      <button
                        onClick={() => navigate({ to: '/contacts/$contactId', params: { contactId: member.id } })}
                        className="p-1.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors opacity-0 group-hover:opacity-100"
                        title="Open contact"
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                      </button>
                      {isManual && (
                        <button
                          onClick={() => removeContact(member.id)}
                          disabled={removingId === member.id}
                          className="p-1.5 rounded hover:bg-red-50 text-muted-foreground hover:text-red-600 transition-colors opacity-0 group-hover:opacity-100"
                          title="Remove from list"
                        >
                          {removingId === member.id ? (
                            <span className="text-xs">…</span>
                          ) : (
                            <X className="h-3.5 w-3.5" />
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Pagination footer */}
        {totalPages > 1 && (
          <div className="px-6 py-3 border-t shrink-0 flex items-center justify-between">
            <span className="text-xs text-muted-foreground">
              Page {page} of {totalPages} · {total.toLocaleString()} total
            </span>
            <div className="flex items-center gap-1">
              <Button
                size="sm"
                variant="outline"
                className="h-7 px-2"
                disabled={page <= 1}
                onClick={() => setPage(p => p - 1)}
              >
                <ChevronLeft className="h-3.5 w-3.5" />
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-7 px-2"
                disabled={page >= totalPages}
                onClick={() => setPage(p => p + 1)}
              >
                <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        )}

        {/* Footer note for filter contacts */}
        <div className="px-6 py-3 border-t shrink-0 bg-muted/20">
          <p className="text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1 text-blue-700 font-medium">⊛ filter</span> contacts are resolved dynamically from your list's filter criteria and cannot be removed individually — update the filters to change them. &nbsp;
            <span className="inline-flex items-center gap-1 text-purple-700 font-medium">✦ manual</span> contacts were added individually and can be removed with ✕.
          </p>
        </div>
      </div>
    </>
  );
}

// ── Create/Edit Drawer ────────────────────────────────────────────────────

type DrawerTab = 'filters' | 'tags' | 'manual';

function ListDrawer({
  editList,
  onClose,
  onSaved,
}: {
  editList: CampaignList | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [step, setStep] = useState(1);
  const [tab, setTab] = useState<DrawerTab>('filters');

  const [name, setName] = useState(editList?.name || '');
  const [description, setDescription] = useState(editList?.description || '');
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>(editList?.filters?.statuses || []);
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>(editList?.filters?.tag_ids || []);
  const [selectedCompanyIds, setSelectedCompanyIds] = useState<string[]>(editList?.filters?.company_ids || []);
  const [manualContactIds, setManualContactIds] = useState<string[]>(editList?.contact_ids || []);
  const [contactSearch, setContactSearch] = useState('');
  const [saving, setSaving] = useState(false);
  const [previewCount, setPreviewCount] = useState<number | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const previewTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setName(editList?.name || '');
    setDescription(editList?.description || '');
    setSelectedStatuses(editList?.filters?.statuses || []);
    setSelectedTagIds(editList?.filters?.tag_ids || []);
    setSelectedCompanyIds(editList?.filters?.company_ids || []);
    setManualContactIds(editList?.contact_ids || []);
    setPreviewCount(null);
    setContactSearch('');
    setStep(1);
    setTab('filters');
  }, [editList]);

  const { data: tags = [] } = useQuery<Tag[]>({
    queryKey: ['tags'],
    queryFn: async () => {
      const res = await api.get('/tags');
      return res.data.data || res.data || [];
    },
  });

  const { data: companies = [] } = useQuery<{ id: string; name: string }[]>({
    queryKey: ['companies-list'],
    queryFn: async () => {
      const res = await api.get('/companies', { params: { per_page: 200 } });
      return res.data.data || res.data || [];
    },
    staleTime: 30_000,
  });

  const { data: searchResults = [] } = useQuery<{ id: string; first_name: string | null; last_name: string | null; email: string | null; status: string | null }[]>({
    queryKey: ['contact-search', contactSearch],
    queryFn: async () => {
      if (!contactSearch || contactSearch.length < 2) return [];
      const res = await api.get('/contacts', { params: { search: contactSearch, per_page: 20 } });
      return (res.data.data || []).map((c: Record<string, unknown>) => ({
        id: c.id as string,
        first_name: c.first_name as string | null,
        last_name: c.last_name as string | null,
        email: c.email as string | null,
        status: c.status as string | null,
      }));
    },
    enabled: contactSearch.length >= 2,
  });

  useEffect(() => {
    const hasAny = selectedStatuses.length > 0 || selectedTagIds.length > 0 || selectedCompanyIds.length > 0 || manualContactIds.length > 0;
    if (!hasAny) { setPreviewCount(null); return; }
    if (previewTimer.current) clearTimeout(previewTimer.current);
    previewTimer.current = setTimeout(async () => {
      setPreviewLoading(true);
      try {
        const res = await api.post('/campaign-lists/preview-filters', {
          name: 'preview',
          filters: { statuses: selectedStatuses, tag_ids: selectedTagIds, company_ids: selectedCompanyIds },
          contact_ids: manualContactIds,
        });
        setPreviewCount(res.data.count);
      } catch { setPreviewCount(null); }
      finally { setPreviewLoading(false); }
    }, 500);
    return () => { if (previewTimer.current) clearTimeout(previewTimer.current); };
  }, [selectedStatuses, selectedTagIds, selectedCompanyIds, manualContactIds]);

  const hasFilters = selectedStatuses.length > 0 || selectedTagIds.length > 0 || selectedCompanyIds.length > 0;
  const hasManual = manualContactIds.length > 0;
  const hasContent = hasFilters || hasManual;

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = {
        name,
        description: description || null,
        filters: { statuses: selectedStatuses, tag_ids: selectedTagIds, company_ids: selectedCompanyIds },
        contact_ids: manualContactIds,
      };
      if (editList) {
        await api.patch(`/campaign-lists/${editList.id}`, payload);
        toast.success('List updated');
      } else {
        await api.post('/campaign-lists', payload);
        toast.success('List created');
      }
      onSaved();
      onClose();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to save list';
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  const toggleStatus = (s: string) =>
    setSelectedStatuses(prev => prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]);

  const toggleTag = (id: string) =>
    setSelectedTagIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);

  const toggleContact = (id: string) =>
    setManualContactIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);

  return (
    <Dialog open onOpenChange={() => onClose()}>
      <DialogContent className="max-w-[600px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{editList ? 'Edit List' : 'New List'}</DialogTitle>
        </DialogHeader>

        {step === 1 && (
          <div className="space-y-4">
            <div>
              <Label>Name <span className="text-red-500">*</span></Label>
              <Input value={name} onChange={e => setName(e.target.value)} placeholder="Q1 Newsletter Prospects" />
            </div>
            <div>
              <Label>Description</Label>
              <Input value={description} onChange={e => setDescription(e.target.value)} placeholder="Optional description..." />
            </div>
            <div className="flex justify-end">
              <Button onClick={() => setStep(2)} disabled={!name.trim()}>
                Next: Define Members →
              </Button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <div className="flex border-b">
              {([
                { key: 'filters' as const, label: 'By Filters' },
                { key: 'tags' as const, label: 'By Tags (Quick)' },
                { key: 'manual' as const, label: 'Manual Selection' },
              ]).map(t => (
                <button
                  key={t.key}
                  onClick={() => setTab(t.key)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                    tab === t.key ? 'border-[#253a52] text-[#253a52]' : 'border-transparent text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {tab === 'filters' && (
              <div className="space-y-4">
                <div>
                  <Label className="text-sm">Contact Status</Label>
                  <div className="flex flex-wrap gap-2 mt-1.5">
                    {ALL_STATUSES.map(s => (
                      <button key={s} onClick={() => toggleStatus(s)}
                        className={`text-xs px-3 py-1.5 rounded-full border transition-colors capitalize ${
                          selectedStatuses.includes(s) ? 'bg-[#253a52] text-white border-[#253a52]' : 'border-gray-300 hover:border-[#253a52]/50'
                        }`}>
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <Label className="text-sm">Tags</Label>
                  <p className="text-xs text-muted-foreground mt-0.5 mb-1.5">Contacts matching any selected tag will be included.</p>
                  <div className="flex flex-wrap gap-2">
                    {tags.map(tag => (
                      <button key={tag.id} onClick={() => toggleTag(tag.id)}
                        className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                          selectedTagIds.includes(tag.id) ? 'bg-[#253a52] text-white border-[#253a52]' : 'border-gray-300 hover:border-[#253a52]/50'
                        }`}>
                        {tag.name} {tag.contact_count != null ? `(${tag.contact_count})` : ''}
                      </button>
                    ))}
                    {tags.length === 0 && <p className="text-xs text-muted-foreground">No tags found</p>}
                  </div>
                </div>
                <div>
                  <Label className="text-sm">Company</Label>
                  <div className="max-h-40 overflow-y-auto border rounded-lg p-2 space-y-1 mt-1.5">
                    {companies.length === 0 ? (
                      <p className="text-xs text-muted-foreground p-2">No companies found</p>
                    ) : companies.map(company => (
                      <label key={company.id} className="flex items-center gap-2 p-1.5 hover:bg-gray-50 rounded cursor-pointer">
                        <input type="checkbox" checked={selectedCompanyIds.includes(company.id)}
                          onChange={() => setSelectedCompanyIds(prev =>
                            prev.includes(company.id) ? prev.filter(x => x !== company.id) : [...prev, company.id]
                          )}
                          className="rounded border-gray-300" />
                        <span className="text-sm">{company.name}</span>
                      </label>
                    ))}
                  </div>
                  {selectedCompanyIds.length > 0 && (
                    <p className="text-xs text-muted-foreground mt-1">{selectedCompanyIds.length} compan{selectedCompanyIds.length !== 1 ? 'ies' : 'y'} selected</p>
                  )}
                </div>
              </div>
            )}

            {tab === 'tags' && (
              <div className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  Select one or more CRM tags — all contacts with <strong>any</strong> of the selected tags will be added to this list.
                </p>
                <p className="text-xs text-muted-foreground">Tags selected here also appear in the Filters tab.</p>
                <div className="flex flex-wrap gap-2">
                  {tags.map(tag => (
                    <button key={tag.id} onClick={() => toggleTag(tag.id)}
                      className={`text-sm px-4 py-2 rounded-lg border transition-colors ${
                        selectedTagIds.includes(tag.id) ? 'bg-[#253a52] text-white border-[#253a52]' : 'border-gray-300 hover:border-[#253a52]/50 hover:bg-gray-50'
                      }`}>
                      {tag.name} {tag.contact_count != null ? `(${tag.contact_count})` : ''}
                    </button>
                  ))}
                  {tags.length === 0 && <p className="text-sm text-muted-foreground">No tags found</p>}
                </div>
                {selectedTagIds.length > 0 && (
                  <p className="text-sm text-blue-600">{selectedTagIds.length} tag{selectedTagIds.length !== 1 ? 's' : ''} selected</p>
                )}
              </div>
            )}

            {tab === 'manual' && (
              <div className="space-y-3">
                <Input value={contactSearch} onChange={e => setContactSearch(e.target.value)}
                  placeholder="Search contacts by name or email..." />
                {searchResults.length > 0 && (
                  <div className="border rounded-lg divide-y max-h-48 overflow-y-auto">
                    {searchResults.map(c => (
                      <label key={c.id} className="flex items-center gap-3 px-3 py-2 hover:bg-gray-50 cursor-pointer">
                        <input type="checkbox" checked={manualContactIds.includes(c.id)}
                          onChange={() => toggleContact(c.id)} className="w-4 h-4 rounded" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{c.first_name || ''} {c.last_name || ''}</p>
                          <p className="text-xs text-muted-foreground truncate">{c.email}</p>
                        </div>
                      </label>
                    ))}
                  </div>
                )}
                {manualContactIds.length > 0 && (
                  <div className="bg-blue-50 text-blue-700 p-3 rounded-lg text-sm">
                    {manualContactIds.length} contact{manualContactIds.length !== 1 ? 's' : ''} manually selected
                    <button className="ml-2 text-blue-500 underline text-xs" onClick={() => setManualContactIds([])}>Clear all</button>
                  </div>
                )}
              </div>
            )}

            {(selectedTagIds.length > 0 || selectedStatuses.length > 0 || selectedCompanyIds.length > 0 || manualContactIds.length > 0) && (
              <div className="flex items-center gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-700">
                <span>👥</span>
                {previewLoading ? (
                  <span>Calculating...</span>
                ) : previewCount != null ? (
                  <span><strong>{previewCount.toLocaleString()}</strong> contacts match these criteria</span>
                ) : (
                  <span>Unable to preview</span>
                )}
              </div>
            )}

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(1)}>← Back</Button>
              <Button onClick={() => setStep(3)} disabled={!hasContent}>Next: Review →</Button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Name</span>
                <span className="font-medium">{name}</span>
              </div>
              {description && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Description</span>
                  <span>{description}</span>
                </div>
              )}
              {selectedStatuses.length > 0 && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Statuses</span>
                  <span className="capitalize">{selectedStatuses.join(', ')}</span>
                </div>
              )}
              {selectedTagIds.length > 0 && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Tags (any match)</span>
                  <span>{tags.filter(t => selectedTagIds.includes(t.id)).map(t => t.name).join(', ') || `${selectedTagIds.length} selected`}</span>
                </div>
              )}
              {selectedCompanyIds.length > 0 && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Companies</span>
                  <span>{companies.filter(c => selectedCompanyIds.includes(c.id)).map(c => c.name).join(', ') || `${selectedCompanyIds.length} selected`}</span>
                </div>
              )}
              {manualContactIds.length > 0 && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Manual contacts</span>
                  <span>{manualContactIds.length}</span>
                </div>
              )}
            </div>
            <Separator />
            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(2)}>← Back</Button>
              <Button onClick={handleSave} disabled={saving} className="bg-[#253a52] hover:bg-[#253a52]/90">
                {saving ? 'Saving...' : editList ? 'Update List' : 'Save List'}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ── Main Lists Page ───────────────────────────────────────────────────────

export default function ListsPage() {
  const queryClient = useQueryClient();
  const [showDrawer, setShowDrawer] = useState(false);
  const [editList, setEditList] = useState<CampaignList | null>(null);
  const [membersDrawerList, setMembersDrawerList] = useState<CampaignList | null>(null);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const isRestricted = useAuth((s) => s.isRestricted);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  useEffect(() => { document.title = 'Lists — Sarson Funds CRM'; }, []);

  const { data: lists = [], isLoading } = useQuery<CampaignList[]>({
    queryKey: ['campaign-lists'],
    queryFn: async () => {
      const res = await api.get('/campaign-lists');
      return res.data || [];
    },
  });

  // Keep membersDrawerList in sync with latest list data from the query
  useEffect(() => {
    if (membersDrawerList) {
      const fresh = lists.find(l => l.id === membersDrawerList.id);
      if (fresh) setMembersDrawerList(fresh);
    }
  }, [lists]);

  const syncToMailchimp = async (id: string) => {
    setSyncingId(id);
    try {
      const res = await api.post(`/campaign-lists/${id}/sync`);
      toast.success(`Synced ${res.data.member_count} contacts to Mailchimp`);
      queryClient.invalidateQueries({ queryKey: ['campaign-lists'] });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Sync failed';
      if (msg?.toLowerCase().includes('not configured') || msg?.toLowerCase().includes('api key')) {
        toast.error('Mailchimp not configured. Add your API key in .env to enable syncing.');
      } else {
        toast.error(msg);
      }
    } finally {
      setSyncingId(null);
    }
  };

  const deleteList = useMutation({
    mutationFn: async (id: string) => { await api.delete(`/campaign-lists/${id}`); },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['campaign-lists'] });
      toast.success('List deleted');
      setDeleteConfirm(null);
    },
    onError: () => toast.error('Failed to delete list'),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Lists</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Saved groups of contacts for email campaigns</p>
        </div>
        <Button onClick={() => { setEditList(null); setShowDrawer(true); }} className="bg-[#253a52] hover:bg-[#253a52]/90">
          + New List
        </Button>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading lists...</p>
      ) : !lists.length ? (
        <Card>
          <CardContent className="py-16 text-center">
            <div className="text-4xl mb-4">📋</div>
            <p className="text-lg font-medium text-muted-foreground mb-2">No lists yet</p>
            <p className="text-sm text-muted-foreground mb-4">Create your first list to start targeting campaigns</p>
            <Button onClick={() => { setEditList(null); setShowDrawer(true); }} className="bg-[#253a52] hover:bg-[#253a52]/90">
              Create Your First List
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Name</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider hidden md:table-cell">Description</th>
                <th className="text-center px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Members</th>
                <th className="text-center px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider hidden sm:table-cell">Mailchimp</th>
                <th className="text-center px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider hidden lg:table-cell">Created</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {lists.map(list => (
                <tr key={list.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <button
                      onClick={() => setMembersDrawerList(list)}
                      className="text-sm font-medium hover:text-[#253a52] hover:underline text-left transition-colors"
                    >
                      {list.name}
                    </button>
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell">
                    <p className="text-sm text-muted-foreground truncate max-w-48">{list.description || '—'}</p>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button
                      onClick={() => setMembersDrawerList(list)}
                      className="inline-flex items-center gap-1 text-sm font-medium hover:text-[#253a52] transition-colors group"
                      title="View members"
                    >
                      {list.member_count.toLocaleString()}
                      <Users className="h-3 w-3 text-muted-foreground group-hover:text-[#253a52] transition-colors" />
                    </button>
                  </td>
                  <td className="px-4 py-3 text-center hidden sm:table-cell">
                    <SyncStatusBadge list={list} />
                  </td>
                  <td className="px-4 py-3 text-center hidden lg:table-cell">
                    <span className="text-xs text-muted-foreground">{formatDate(list.created_at)}</span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      <Button size="sm" variant="outline" onClick={() => setMembersDrawerList(list)}>
                        Members
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => { setEditList(list); setShowDrawer(true); }}>
                        Edit
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => syncToMailchimp(list.id)} disabled={syncingId === list.id}>
                        {syncingId === list.id ? '⟳' : '↑'} Sync
                      </Button>
                      {!isRestricted && <Button size="sm" variant="outline" className="text-red-600 hover:text-red-700" onClick={() => setDeleteConfirm(list.id)}>
                        Delete
                      </Button>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Members drawer */}
      {membersDrawerList && (
        <ListMembersDrawer
          list={membersDrawerList}
          onClose={() => setMembersDrawerList(null)}
          onMembersChanged={() => queryClient.invalidateQueries({ queryKey: ['campaign-lists'] })}
        />
      )}

      {/* Create/Edit drawer */}
      {showDrawer && (
        <ListDrawer
          editList={editList}
          onClose={() => { setShowDrawer(false); setEditList(null); }}
          onSaved={() => queryClient.invalidateQueries({ queryKey: ['campaign-lists'] })}
        />
      )}

      {/* Delete confirmation */}
      <Dialog open={!!deleteConfirm} onOpenChange={() => setDeleteConfirm(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Delete List</DialogTitle></DialogHeader>
          <p className="text-sm text-muted-foreground">Are you sure you want to delete this list? This cannot be undone.</p>
          <div className="flex justify-end gap-2 mt-4">
            <Button variant="outline" onClick={() => setDeleteConfirm(null)}>Cancel</Button>
            <Button className="bg-red-600 hover:bg-red-700 text-white"
              onClick={() => deleteConfirm && deleteList.mutate(deleteConfirm)}
              disabled={deleteList.isPending}>
              Delete
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
