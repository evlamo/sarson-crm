import { useState, useRef, useEffect, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Trash2, Tag, Search, X, Check, Loader2, UserMinus } from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Separator } from '@/components/ui/separator';

interface TagWithCount {
  id: string;
  name: string;
  color: string | null;
  contact_count: number;
}

interface ContactTag {
  id: string;
  name: string;
}

interface ContactResult {
  id: string;
  first_name: string | null;
  last_name: string | null;
  full_name: string;
  email: string | null;
  company_name: string | null;
  tags: ContactTag[];
}

interface PaginatedContacts {
  data: ContactResult[];
  total: number;
  page: number;
  per_page: number;
}

function useDebounce(value: string, delay: number) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

function getInitials(first: string | null, last: string | null): string {
  return ((first?.[0] || '') + (last?.[0] || '')).toUpperCase() || '?';
}

// ── Tag Contacts Drawer ───────────────────────────────────────────────────

function TagContactsDrawer({
  tag,
  open,
  onClose,
}: {
  tag: TagWithCount;
  open: boolean;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [tagSearch, setTagSearch] = useState('');
  const [addSearch, setAddSearch] = useState('');
  const [justAdded, setJustAdded] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [removingIds, setRemovingIds] = useState<Set<string>>(new Set());
  const [addingIds, setAddingIds] = useState<Set<string>>(new Set());

  const debouncedTagSearch = useDebounce(tagSearch, 300);
  const debouncedAddSearch = useDebounce(addSearch, 300);

  // Reset state when tag changes or drawer closes
  useEffect(() => {
    setTagSearch('');
    setAddSearch('');
    setJustAdded(null);
    setMutationError(null);
    setRemovingIds(new Set());
    setAddingIds(new Set());
  }, [tag.id]);

  useEffect(() => {
    if (!open) {
      setTagSearch('');
      setAddSearch('');
      setJustAdded(null);
      setMutationError(null);
      setRemovingIds(new Set());
      setAddingIds(new Set());
    }
  }, [open]);

  // Contacts with this tag (H1: per_page 500)
  const { data: tagContacts, isLoading: loadingTagContacts } = useQuery<PaginatedContacts>({
    queryKey: ['tag-contacts', tag.id, debouncedTagSearch],
    queryFn: async () => {
      const params: Record<string, string | number> = { tag_id: tag.id, per_page: 500 };
      if (debouncedTagSearch) params.search = debouncedTagSearch;
      const res = await api.get('/contacts', { params });
      return res.data;
    },
    enabled: open,
  });

  // All contacts search (for adding) — always live, shows untagged contacts immediately
  const { data: searchResults, isLoading: loadingSearch } = useQuery<PaginatedContacts>({
    queryKey: ['contact-search', debouncedAddSearch],
    queryFn: async () => {
      const res = await api.get('/contacts', {
        params: { search: debouncedAddSearch || undefined, per_page: 50 },
      });
      return res.data;
    },
    enabled: open,
  });

  const tagContactIds = new Set(tagContacts?.data.map((c) => c.id) || []);

  // Filter out contacts already tagged — always visible, live search
  const addCandidates = (searchResults?.data || [])
    .filter((c) => !tagContactIds.has(c.id))
    .slice(0, 20);

  const showError = (msg: string) => {
    setMutationError(msg);
    setTimeout(() => setMutationError(null), 4000);
  };

  // Add tag to contact
  const addMutation = useMutation({
    mutationFn: async (contactId: string) => {
      setAddingIds((prev) => new Set(prev).add(contactId));
      await api.post('/contacts/bulk', { ids: [contactId], tag_ids: [tag.id] });
    },
    onSuccess: (_data, contactId) => {
      setAddingIds((prev) => { const n = new Set(prev); n.delete(contactId); return n; });
      setJustAdded(contactId);
      setAddSearch('');
      setTimeout(() => setJustAdded(null), 1000);
      queryClient.invalidateQueries({ queryKey: ['tag-contacts', tag.id] });
      queryClient.invalidateQueries({ queryKey: ['tags', 'with-counts'] });
    },
    onError: (_err, contactId) => {
      setAddingIds((prev) => { const n = new Set(prev); n.delete(contactId); return n; });
      showError('Failed to add contact. Please try again.');
    },
  });

  // Remove tag from contact
  const removeMutation = useMutation({
    mutationFn: async (contactId: string) => {
      setRemovingIds((prev) => new Set(prev).add(contactId));
      await api.delete(`/contacts/${contactId}/tags/${tag.id}`);
    },
    onSuccess: (_data, contactId) => {
      setRemovingIds((prev) => { const n = new Set(prev); n.delete(contactId); return n; });
      queryClient.invalidateQueries({ queryKey: ['tag-contacts', tag.id] });
      queryClient.invalidateQueries({ queryKey: ['tags', 'with-counts'] });
    },
    onError: (_err, contactId) => {
      setRemovingIds((prev) => { const n = new Set(prev); n.delete(contactId); return n; });
      showError('Failed to remove contact. Please try again.');
    },
  });

  const contacts = tagContacts?.data || [];

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent side="right" className="w-[380px] sm:w-[420px] flex flex-col p-0 gap-0">

        {/* Header */}
        <SheetHeader className="px-5 pt-5 pb-3 border-b shrink-0">
          <SheetTitle className="flex items-center gap-2 text-sm font-semibold">
            <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: tag.color || '#6b7280' }} />
            {tag.name}
            <span className="ml-auto text-xs font-normal text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
              {tagContacts?.total ?? tag.contact_count} tagged
            </span>
          </SheetTitle>
        </SheetHeader>

        {/* ── Section 1: In this tag ── */}
        <div className="px-5 pt-4 pb-2 shrink-0">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">In this tag</p>
          <div className="relative">
            <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              value={tagSearch}
              onChange={(e) => setTagSearch(e.target.value)}
              placeholder="Find someone..."
              className="pl-8 h-8 text-sm"
            />
          </div>
        </div>

        <div className="overflow-y-auto px-5 pb-3" style={{ maxHeight: '35vh' }}>
          {loadingTagContacts ? (
            <div className="space-y-2">
              {[1,2,3].map(i => <div key={i} className="h-9 bg-muted rounded animate-pulse" />)}
            </div>
          ) : contacts.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-6">
              {debouncedTagSearch ? 'No matches' : 'Nobody tagged yet'}
            </p>
          ) : (
            <div className="space-y-0.5">
              {contacts.map((contact) => (
                <div key={contact.id} className="flex items-center gap-2.5 rounded-md px-2 py-1.5 group hover:bg-muted/50 transition-colors">
                  <div className="w-7 h-7 rounded-full bg-[#253a52]/10 text-[#253a52] flex items-center justify-center text-xs font-semibold shrink-0">
                    {getInitials(contact.first_name, contact.last_name)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium truncate">{contact.full_name}</p>
                    <p className="text-xs text-muted-foreground truncate">{contact.email}</p>
                  </div>
                  <button
                    className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-all p-1 rounded shrink-0"
                    onClick={() => removeMutation.mutate(contact.id)}
                    disabled={removingIds.has(contact.id)}
                    title="Remove from tag"
                  >
                    {removingIds.has(contact.id) ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <UserMinus className="h-3.5 w-3.5" />}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <Separator className="shrink-0" />

        {/* ── Section 2: Add people ── */}
        <div className="px-5 pt-4 pb-2 shrink-0">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Add people</p>
          <div className="relative">
            <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              value={addSearch}
              onChange={(e) => setAddSearch(e.target.value)}
              placeholder="Search contacts..."
              className="pl-8 h-8 text-sm"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-5 pb-5">
          {loadingSearch ? (
            <div className="space-y-2">
              {[1,2,3].map(i => <div key={i} className="h-9 bg-muted rounded animate-pulse" />)}
            </div>
          ) : addCandidates.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-6">
              {debouncedAddSearch ? 'No matches' : 'All contacts already tagged'}
            </p>
          ) : (
            <div className="space-y-0.5">
              {addCandidates.map((contact) => (
                <div
                  key={contact.id}
                  className="flex items-center gap-2.5 rounded-md px-2 py-1.5 group hover:bg-muted/40 transition-colors"
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => { if (e.key === 'Enter') addMutation.mutate(contact.id); }}
                >
                  <div className="w-7 h-7 rounded-full bg-muted text-muted-foreground flex items-center justify-center text-xs font-semibold shrink-0">
                    {getInitials(contact.first_name, contact.last_name)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium truncate">{contact.full_name}</p>
                    <p className="text-xs text-muted-foreground truncate">{contact.email}</p>
                  </div>
                  <button
                    className="opacity-0 group-hover:opacity-100 shrink-0 text-xs font-medium text-[#253a52] transition-all px-2 py-0.5 rounded border border-[#253a52]/40 hover:bg-[#253a52] hover:text-white"
                    onClick={() => addMutation.mutate(contact.id)}
                    disabled={addingIds.has(contact.id)}
                  >
                    {addingIds.has(contact.id)
                      ? <Loader2 className="h-3 w-3 animate-spin" />
                      : justAdded === contact.id
                      ? <Check className="h-3 w-3 text-green-500" />
                      : '+ Add'}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {mutationError && (
          <p className="px-5 pb-3 text-xs text-destructive shrink-0">{mutationError}</p>
        )}

      </SheetContent>
    </Sheet>
  );
}

// ── Main Tags Page ────────────────────────────────────────────────────────

export default function TagsPage() {
  const queryClient = useQueryClient();
  const [newTagName, setNewTagName] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<TagWithCount | null>(null);
  const [selectedTag, setSelectedTag] = useState<TagWithCount | null>(null);
  const editRef = useRef<HTMLInputElement>(null);

  useEffect(() => { document.title = 'Tags — Sarson Funds CRM'; }, []);

  const { data: tags = [], isLoading } = useQuery<TagWithCount[]>({
    queryKey: ['tags', 'with-counts'],
    queryFn: async () => {
      const res = await api.get('/tags', { params: { with_counts: true } });
      return res.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (name: string) => {
      await api.post('/tags', { name });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tags'] });
      setNewTagName('');
    },
  });

  const renameMutation = useMutation({
    mutationFn: async ({ id, name }: { id: string; name: string }) => {
      await api.patch(`/tags/${id}`, { name });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tags'] });
      setEditingId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/tags/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tags'] });
      setDeleteTarget(null);
    },
  });

  const startEdit = (tag: TagWithCount) => {
    setEditingId(tag.id);
    setEditDraft(tag.name);
    setTimeout(() => editRef.current?.focus(), 0);
  };

  const saveEdit = (id: string) => {
    const trimmed = editDraft.trim();
    if (trimmed && trimmed !== tags.find(t => t.id === id)?.name) {
      renameMutation.mutate({ id, name: trimmed });
    } else {
      setEditingId(null);
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold">Tags</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Manage contact tags</p>
      </div>

      {/* Create new tag */}
      <Card>
        <CardContent className="pt-6">
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (newTagName.trim()) createMutation.mutate(newTagName.trim());
            }}
          >
            <Input
              value={newTagName}
              onChange={(e) => setNewTagName(e.target.value)}
              placeholder="New tag name..."
              className="flex-1"
            />
            <Button type="submit" disabled={!newTagName.trim() || createMutation.isPending}>
              Create
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Tags list */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Tag className="h-4 w-4" />
            All Tags ({tags.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-10 bg-muted rounded animate-pulse" />
              ))}
            </div>
          ) : tags.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">No tags yet. Create one above.</p>
          ) : (
            <div className="divide-y">
              {tags.map((tag) => (
                <div key={tag.id} className="flex items-center justify-between py-3 group">
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <span
                      className="w-3 h-3 rounded-full shrink-0"
                      style={{ backgroundColor: tag.color || '#6b7280' }}
                    />
                    {editingId === tag.id ? (
                      <input
                        ref={editRef}
                        value={editDraft}
                        onChange={(e) => setEditDraft(e.target.value)}
                        onBlur={() => saveEdit(tag.id)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') saveEdit(tag.id);
                          if (e.key === 'Escape') setEditingId(null);
                        }}
                        className="flex-1 h-7 px-2 text-sm border rounded bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                      />
                    ) : (
                      <span
                        className="text-sm font-medium cursor-pointer hover:underline"
                        onClick={() => startEdit(tag)}
                      >
                        {tag.name}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <button
                      className="text-xs text-[#253a52] hover:underline font-medium cursor-pointer"
                      onClick={() => setSelectedTag(tag)}
                    >
                      {tag.contact_count} contact{tag.contact_count !== 1 ? 's' : ''}
                    </button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive"
                      onClick={() => setDeleteTarget(tag)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete confirmation */}
      <Dialog open={!!deleteTarget} onOpenChange={(v) => !v && setDeleteTarget(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-destructive">Delete tag "{deleteTarget?.name}"?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            This will remove the tag from {deleteTarget?.contact_count || 0} contact{deleteTarget?.contact_count !== 1 ? 's' : ''}. This cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button
              variant="destructive"
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Tag contacts drawer */}
      {selectedTag && (
        <TagContactsDrawer
          tag={selectedTag}
          open={!!selectedTag}
          onClose={() => setSelectedTag(null)}
        />
      )}
    </div>
  );
}
