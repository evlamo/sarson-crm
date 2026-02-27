import { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from '@tanstack/react-router';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
  type RowSelectionState,
} from '@tanstack/react-table';
import api from '@/lib/api';
import type { Contact, PaginatedResponse } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Search, UserPlus, Tag, Download, Trash2, X } from 'lucide-react';

// ─── Add Contact Modal ────────────────────────────────────────────────────────
const EMPTY_FORM = {
  first_name: '',
  last_name: '',
  company: '',
  email: '',
  middle_name: '',
  title: '',
  phone: '',
  status: 'active',
  source: '',
  sarson_rep: '',
  next_step: '',
  last_contacted_at: '',
  notes: '',
  linkedin_url: '',
  website: '',
  city: '',
  state: '',
  country: '',
};

type FormState = typeof EMPTY_FORM;

function AddContactModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({});
  const [saveError, setSaveError] = useState('');

  const set = (field: keyof FormState) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const mutation = useMutation({
    mutationFn: async (payload: Record<string, unknown>) => {
      const res = await api.post('/contacts', payload);
      // If a note was included, post it as an activity log entry too
      if (payload.notes && res.data?.id) {
        await api.post(`/contacts/${res.data.id}/activities`, {
          activity_type: 'note',
          body: payload.notes,
        });
      }
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
      setForm(EMPTY_FORM);
      setErrors({});
      setSaveError('');
      onClose();
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setSaveError(msg || 'Failed to save — please try again.');
    },
  });

  const validate = () => {
    const e: Partial<Record<keyof FormState, string>> = {};
    if (!form.first_name.trim()) e.first_name = 'Required';
    if (!form.last_name.trim()) e.last_name = 'Required';
    if (!form.company.trim()) e.company = 'Required';
    if (!form.email.trim()) e.email = 'Required';
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) e.email = 'Invalid email';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSaveError('');
    if (!validate()) return;
    const payload: Record<string, unknown> = {};
    (Object.keys(form) as (keyof FormState)[]).forEach((k) => {
      const v = form[k].trim();
      if (v !== '') payload[k] = v;
    });
    // Always send status even if default
    payload.status = form.status;
    mutation.mutate(payload);
  };

  const handleClose = () => {
    setForm(EMPTY_FORM);
    setErrors({});
    setSaveError('');
    onClose();
  };

  const field = (
    label: string,
    key: keyof FormState,
    opts?: { required?: boolean; type?: string; placeholder?: string }
  ) => (
    <div className="space-y-1">
      <Label htmlFor={key} className="text-sm font-medium">
        {label}{opts?.required && <span className="text-destructive ml-0.5">*</span>}
      </Label>
      <Input
        id={key}
        type={opts?.type || 'text'}
        value={form[key]}
        onChange={set(key)}
        placeholder={opts?.placeholder || ''}
        className={errors[key] ? 'border-destructive focus-visible:ring-destructive' : ''}
      />
      {errors[key] && <p className="text-xs text-destructive">{errors[key]}</p>}
    </div>
  );

  return (
    <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <UserPlus className="h-5 w-5" />
            Add New Contact
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Required */}
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">Required</p>
            <div className="grid grid-cols-2 gap-4">
              {field('First Name', 'first_name', { required: true, placeholder: 'John' })}
              {field('Last Name', 'last_name', { required: true, placeholder: 'Smith' })}
              {field('Company', 'company', { required: true, placeholder: 'Acme Capital' })}
              {field('Email', 'email', { required: true, type: 'email', placeholder: 'john@acme.com' })}
            </div>
          </div>

          {/* Contact Details */}
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">Contact Details</p>
            <div className="grid grid-cols-2 gap-4">
              {field('Middle Name', 'middle_name')}
              {field('Position / Title', 'title', { placeholder: 'Portfolio Manager' })}
              {field('Phone', 'phone', { type: 'tel', placeholder: '+1 (312) 555-0100' })}
              <div className="space-y-1">
                <Label className="text-sm font-medium">Status</Label>
                <select
                  value={form.status}
                  onChange={set('status')}
                  className="w-full h-9 px-3 text-sm border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  {STATUSES.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </div>
              {field('Source', 'source', { placeholder: 'Conference, referral...' })}
            </div>
          </div>

          {/* Assignment */}
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">Assignment</p>
            <div className="grid grid-cols-2 gap-4">
              {field('Sales Rep', 'sarson_rep', { placeholder: 'Assign a rep...' })}
              {field('Next Step', 'next_step', { placeholder: 'Schedule intro call...' })}
              {field('Last Contacted', 'last_contacted_at', { type: 'date' })}
            </div>
          </div>

          {/* Online */}
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">Online</p>
            <div className="grid grid-cols-2 gap-4">
              {field('LinkedIn URL', 'linkedin_url', { placeholder: 'https://linkedin.com/in/...' })}
              {field('Website', 'website', { placeholder: 'https://...' })}
            </div>
          </div>

          {/* Location */}
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">Location</p>
            <div className="grid grid-cols-3 gap-4">
              {field('City', 'city', { placeholder: 'Chicago' })}
              {field('State', 'state', { placeholder: 'IL' })}
              {field('Country', 'country', { placeholder: 'US' })}
            </div>
          </div>

          {/* Notes */}
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">Notes</p>
            <textarea
              value={form.notes}
              onChange={set('notes')}
              placeholder="How you met, background context, anything relevant..."
              rows={3}
              className="w-full px-3 py-2 text-sm border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-primary resize-none"
            />
            <p className="text-xs text-muted-foreground mt-1">This will appear in the contact's Notes & Activity timeline.</p>
          </div>

          {saveError && (
            <p className="text-sm text-destructive text-center">{saveError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleClose}>Cancel</Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? 'Saving...' : 'Add Contact'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// Inline editable Last Contact cell — date picker
function InlineLastContact({ contact }: { contact: Contact }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const mutation = useMutation({
    mutationFn: async (value: string) => {
      await api.patch(`/contacts/${contact.id}`, { last_contacted_at: value || null });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
      queryClient.invalidateQueries({ queryKey: ['contact', contact.id] });
      setEditing(false);
    },
  });

  const start = (e: React.MouseEvent) => {
    e.stopPropagation();
    const iso = contact.last_contacted_at ? contact.last_contacted_at.slice(0, 10) : '';
    setDraft(iso);
    setEditing(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const save = () => {
    const current = contact.last_contacted_at ? contact.last_contacted_at.slice(0, 10) : '';
    if (draft !== current) mutation.mutate(draft);
    else setEditing(false);
  };

  if (editing) {
    return (
      <input
        ref={inputRef}
        type="date"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={save}
        onKeyDown={(e) => {
          if (e.key === 'Enter') { e.preventDefault(); save(); }
          if (e.key === 'Escape') setEditing(false);
          e.stopPropagation();
        }}
        onClick={(e) => e.stopPropagation()}
        className="w-full h-7 px-2 text-sm border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-primary"
      />
    );
  }

  const display = contact.last_contacted_at
    ? new Date(contact.last_contacted_at).toLocaleDateString()
    : null;

  return (
    <span
      onClick={start}
      className={`block w-full truncate text-sm cursor-pointer rounded px-1 -mx-1 hover:bg-muted transition-colors ${
        display ? '' : 'text-muted-foreground italic'
      }`}
      title={display || 'Click to set date...'}
    >
      {display || '—'}
    </span>
  );
}

// Inline editable Next Step cell
function InlineNextStep({ contact }: { contact: Contact }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const mutation = useMutation({
    mutationFn: async (value: string) => {
      await api.patch(`/contacts/${contact.id}`, { next_step: value || null });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
      queryClient.invalidateQueries({ queryKey: ['contact', contact.id] });
      setEditing(false);
    },
  });

  const start = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDraft(contact.next_step || '');
    setEditing(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const save = () => {
    if (draft !== (contact.next_step || '')) {
      mutation.mutate(draft);
    } else {
      setEditing(false);
    }
  };

  if (editing) {
    return (
      <input
        ref={inputRef}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={save}
        onKeyDown={(e) => {
          if (e.key === 'Enter') { e.preventDefault(); save(); }
          if (e.key === 'Escape') setEditing(false);
          e.stopPropagation();
        }}
        onClick={(e) => e.stopPropagation()}
        className="w-full h-7 px-2 text-sm border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-primary"
        placeholder="Add next step..."
      />
    );
  }

  return (
    <span
      onClick={start}
      className={`block w-full truncate text-sm cursor-pointer rounded px-1 -mx-1 hover:bg-muted transition-colors ${
        contact.next_step ? '' : 'text-muted-foreground italic'
      }`}
      title={contact.next_step || 'Click to add...'}
    >
      {contact.next_step || '—'}
    </span>
  );
}

// Inline editable Sales Rep cell — single field, compact
function InlineSalesRep({ contact }: { contact: Contact }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const mutation = useMutation({
    mutationFn: async (value: string) => {
      await api.patch(`/contacts/${contact.id}`, { sarson_rep: value || null });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
      queryClient.invalidateQueries({ queryKey: ['contact', contact.id] });
      setEditing(false);
    },
  });

  const start = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDraft(contact.sarson_rep || '');
    setEditing(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const save = () => {
    if (draft !== (contact.sarson_rep || '')) mutation.mutate(draft);
    else setEditing(false);
  };

  if (editing) {
    return (
      <input
        ref={inputRef}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={save}
        onKeyDown={(e) => {
          if (e.key === 'Enter') { e.preventDefault(); save(); }
          if (e.key === 'Escape') setEditing(false);
          e.stopPropagation();
        }}
        onClick={(e) => e.stopPropagation()}
        placeholder="Assign rep..."
        className="w-full h-7 px-2 text-sm border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-primary"
      />
    );
  }

  return (
    <span
      onClick={start}
      className={`block w-full truncate text-sm cursor-pointer rounded px-1 -mx-1 hover:bg-muted transition-colors ${
        contact.sarson_rep ? '' : 'text-muted-foreground italic'
      }`}
      title={contact.sarson_rep || 'Click to assign...'}
    >
      {contact.sarson_rep || '—'}
    </span>
  );
}

const STATUSES = [
  { value: 'hot',       label: 'Hot',       dot: 'bg-red-500' },
  { value: 'warm',      label: 'Warm',      dot: 'bg-orange-400' },
  { value: 'prospect',  label: 'Prospect',  dot: 'bg-yellow-400' },
  { value: 'cold',      label: 'Cold',      dot: 'bg-blue-400' },
  { value: 'poc',       label: 'POC',       dot: 'bg-purple-500' },
  { value: 'active',    label: 'Active',    dot: 'bg-green-500' },
  { value: 'na',        label: 'N/A',       dot: 'bg-gray-300' },
];

const STATUS_MAP = Object.fromEntries(STATUSES.map((s) => [s.value, s]));

const getStatusMeta = (val: string) =>
  STATUS_MAP[val] ?? { label: val, dot: 'bg-gray-300' };

function InlineStatus({ contact }: { contact: Contact }) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: async (value: string) => {
      await api.patch(`/contacts/${contact.id}`, { status: value });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
      queryClient.invalidateQueries({ queryKey: ['contact', contact.id] });
    },
  });

  const meta = getStatusMeta(contact.status);

  return (
    <div className="flex items-center gap-1.5">
      <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${meta.dot}`} />
      <select
        value={contact.status}
        onChange={(e) => { e.stopPropagation(); mutation.mutate(e.target.value); }}
        onClick={(e) => e.stopPropagation()}
        className={`text-xs bg-transparent border-none outline-none cursor-pointer w-full ${mutation.isPending ? 'opacity-60' : ''}`}
      >
        {STATUSES.map((s) => (
          <option key={s.value} value={s.value}>{s.label}</option>
        ))}
      </select>
    </div>
  );
}

// ─── Tag Modal ────────────────────────────────────────────────────────────────
function TagModal({ open, onClose, contactIds }: { open: boolean; onClose: () => void; contactIds: string[] }) {
  const queryClient = useQueryClient();
  const [newTagName, setNewTagName] = useState('');
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: existingTags = [] } = useQuery<{ id: string; name: string; color: string }[]>({
    queryKey: ['tags'],
    queryFn: async () => { const r = await api.get('/tags'); return r.data; },
    enabled: open,
  });

  const createTagMutation = useMutation({
    mutationFn: async (name: string) => { const r = await api.post('/tags', { name }); return r.data; },
    onSuccess: (tag) => {
      queryClient.invalidateQueries({ queryKey: ['tags'] });
      setSelectedTagIds((prev) => [...prev, tag.id]);
      setNewTagName('');
    },
  });

  const applyMutation = useMutation({
    mutationFn: async () => {
      await api.post('/contacts/bulk', { ids: contactIds, tag_ids: selectedTagIds });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
      setSelectedTagIds([]);
      setNewTagName('');
      onClose();
    },
  });

  const toggleTag = (id: string) =>
    setSelectedTagIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);

  const handleCreateTag = () => {
    const name = newTagName.trim();
    if (!name) return;
    createTagMutation.mutate(name);
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Tag className="h-4 w-4" />
            Add Tags — {contactIds.length} contact{contactIds.length !== 1 ? 's' : ''}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Create new tag */}
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Create New Tag</p>
            <div className="flex gap-2">
              <Input
                ref={inputRef}
                value={newTagName}
                onChange={(e) => setNewTagName(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleCreateTag(); } }}
                placeholder="Tag name..."
                className="flex-1"
              />
              <Button size="sm" onClick={handleCreateTag} disabled={!newTagName.trim() || createTagMutation.isPending}>
                Create
              </Button>
            </div>
          </div>

          {/* Existing tags */}
          {existingTags.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Add Existing Tag</p>
              <div className="flex flex-wrap gap-2 max-h-48 overflow-y-auto">
                {existingTags.map((tag) => {
                  const selected = selectedTagIds.includes(tag.id);
                  return (
                    <button
                      key={tag.id}
                      onClick={() => toggleTag(tag.id)}
                      className={`px-3 py-1 rounded-full text-sm border transition-colors ${
                        selected
                          ? 'bg-primary text-primary-foreground border-primary'
                          : 'bg-background border-border hover:bg-muted'
                      }`}
                    >
                      {tag.name}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button
            onClick={() => applyMutation.mutate()}
            disabled={selectedTagIds.length === 0 || applyMutation.isPending}
          >
            {applyMutation.isPending ? 'Applying...' : `Apply to ${contactIds.length} contact${contactIds.length !== 1 ? 's' : ''}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── CSV Export ───────────────────────────────────────────────────────────────
function exportToCSV(contacts: Contact[]) {
  const headers = [
    'First Name', 'Last Name', 'Email', 'Phone', 'Company', 'Title',
    'Status', 'Sales Rep', 'Next Step', 'Last Contacted', 'Source', 'City', 'State', 'Country',
  ];
  const rows = contacts.map((c) => [
    c.first_name || '',
    c.last_name || '',
    c.email || '',
    c.phone || '',
    c.company_name || c.company || '',
    c.title || '',
    c.status || '',
    c.sarson_rep || '',
    c.next_step || '',
    c.last_contacted_at ? new Date(c.last_contacted_at).toLocaleDateString() : '',
    c.source || '',
    c.city || '',
    c.state || '',
    c.country || '',
  ]);

  const csv = [headers, ...rows]
    .map((row) => row.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(','))
    .join('\n');

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `contacts-export-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ─── useWindowWidth ───────────────────────────────────────────────────────────
function useWindowWidth() {
  const [width, setWidth] = useState(typeof window !== 'undefined' ? window.innerWidth : 1280);
  useEffect(() => {
    const handler = () => setWidth(window.innerWidth);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);
  return width;
}

// ─── Delete Confirmation Dialog ───────────────────────────────────────────────
function DeleteConfirmDialog({
  open, count, onConfirm, onCancel, isPending,
}: { open: boolean; count: number; onConfirm: () => void; onCancel: () => void; isPending: boolean }) {
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onCancel()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-destructive">
            <Trash2 className="h-5 w-5" /> Delete {count} Contact{count !== 1 ? 's' : ''}?
          </DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          This will permanently remove {count === 1 ? 'this contact' : `these ${count} contacts`} from the CRM. This action cannot be undone.
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={onCancel} disabled={isPending}>Cancel</Button>
          <Button variant="destructive" onClick={onConfirm} disabled={isPending}>
            {isPending ? 'Deleting...' : `Delete ${count} Contact${count !== 1 ? 's' : ''}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function ContactsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const windowWidth = useWindowWidth();
  const [page, setPage] = useState(1);
  const [limit] = useState(50);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [sorting, setSorting] = useState<SortingState>([]);
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [salesRepFilter, setSalesRepFilter] = useState<string>('');
  const [addContactOpen, setAddContactOpen] = useState(false);
  const [tagModalOpen, setTagModalOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  // Responsive column visibility
  const columnVisibility = useMemo(() => ({
    title:            windowWidth >= 1280,
    phone:            windowWidth >= 1280,
    last_contacted_at: windowWidth >= 1024,
    next_step:        windowWidth >= 1024,
    sarson_rep:       windowWidth >= 768,
  }), [windowWidth]);

  // Bulk delete mutation
  const deleteMutation = useMutation({
    mutationFn: async (ids: string[]) => {
      await Promise.all(ids.map((id) => api.delete(`/contacts/${id}`)));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
      setRowSelection({});
      setDeleteOpen(false);
    },
  });

  // Debounced search — 300ms
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  // Set page title
  useEffect(() => { document.title = 'Contacts — Sarson Funds CRM'; }, []);

  // Map frontend column ids to backend sortable fields
  const SORT_FIELD_MAP: Record<string, string> = {
    full_name: 'last_name',
    first_name: 'first_name',
    last_name: 'last_name',
    company_name: 'company',
    last_contacted_at: 'last_contacted_at',
    title: 'title',
    email: 'email',
    phone: 'phone',
    next_step: 'next_step',
    contacted: 'contacted',
    status: 'status',
  };
  const rawSortField = sorting[0]?.id || 'last_name'; // default sort: last name A→Z
  const sortField = SORT_FIELD_MAP[rawSortField] || rawSortField;
  const sortOrder = sorting[0]?.desc ? 'desc' : 'asc';

  const { data, isLoading } = useQuery({
    queryKey: ['contacts', page, limit, search, sortField, sortOrder, statusFilter, salesRepFilter],
    queryFn: async () => {
      const params: Record<string, string> = {
        page: String(page),
        per_page: String(limit),
        sort: sortField,
        order: sortOrder,
      };
      if (search) params.search = search;
      if (statusFilter !== 'all') params.status = statusFilter;
      if (salesRepFilter.trim()) params.sarson_rep = salesRepFilter.trim();

      const res = await api.get<PaginatedResponse<Contact>>('/contacts', { params });
      return res.data;
    },
  });

  const columns = useMemo<ColumnDef<Contact>[]>(
    () => [
      {
        id: 'select',
        header: ({ table }) => (
          <Checkbox
            checked={table.getIsAllPageRowsSelected()}
            onCheckedChange={(v) => table.toggleAllPageRowsSelected(!!v)}
          />
        ),
        cell: ({ row }) => (
          <Checkbox
            checked={row.getIsSelected()}
            onCheckedChange={(v) => row.toggleSelected(!!v)}
          />
        ),
        enableSorting: false,
        size: 40,
      },
      {
        id: 'full_name',
        header: 'Name',
        size: 180,
        enableSorting: true,
        cell: ({ row }) => {
          const first = row.original.first_name || '';
          const last = row.original.last_name || '';
          const name = [first, last].filter(Boolean).join(' ') || '—';
          return <span className="font-medium text-foreground">{name}</span>;
        },
      },
      {
        accessorKey: 'company_name',
        header: 'Company',
        size: 160,
        cell: ({ getValue }) => (
          <span className="text-foreground/80">{getValue<string | null>() || '—'}</span>
        ),
      },
      {
        accessorKey: 'title',
        header: 'Position',
        size: 150,
        cell: ({ getValue }) => (
          <span className="text-muted-foreground text-sm">{getValue<string | null>() || '—'}</span>
        ),
      },
      {
        accessorKey: 'email',
        header: 'Email',
        size: 210,
        cell: ({ getValue }) => (
          <span className="text-muted-foreground text-sm">{getValue<string | null>() || '—'}</span>
        ),
      },
      {
        accessorKey: 'phone',
        header: 'Phone',
        size: 130,
        cell: ({ getValue }) => (
          <span className="text-muted-foreground text-sm">{getValue<string | null>() || '—'}</span>
        ),
      },
      {
        accessorKey: 'last_contacted_at',
        header: 'Last Contact',
        size: 130,
        cell: ({ row }) => <InlineLastContact contact={row.original} />,
      },
      {
        accessorKey: 'next_step',
        header: 'Next Step',
        size: 200,
        cell: ({ row }) => <InlineNextStep contact={row.original} />,
      },
      {
        accessorKey: 'sarson_rep',
        header: 'Sales Rep',
        size: 150,
        cell: ({ row }) => <InlineSalesRep contact={row.original} />,
      },
      {
        accessorKey: 'status',
        header: 'Status',
        size: 130,
        cell: ({ row }) => <InlineStatus contact={row.original} />,
      },
    ],
    []
  );

  const table = useReactTable({
    data: data?.data || [],
    columns,
    state: { sorting, rowSelection, columnVisibility },
    onSortingChange: setSorting,
    onRowSelectionChange: setRowSelection,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    manualPagination: true,
    pageCount: data ? Math.ceil(data.total / (data.per_page || limit)) : 0,
    enableRowSelection: true,
  });

  const selectedCount = Object.keys(rowSelection).length;
  const totalPages = data ? Math.ceil(data.total / limit) : 0;
  const total = data?.total || 0;
  const startItem = total > 0 ? (page - 1) * limit + 1 : 0;
  const endItem = Math.min(page * limit, total);

  const selectedContacts = table.getSelectedRowModel().rows.map((r) => r.original);
  const selectedIds = selectedContacts.map((c) => c.id);

  return (
    <div className="space-y-4">
      <AddContactModal open={addContactOpen} onClose={() => setAddContactOpen(false)} />
      <TagModal
        open={tagModalOpen}
        onClose={() => { setTagModalOpen(false); setRowSelection({}); }}
        contactIds={selectedIds}
      />
      <DeleteConfirmDialog
        open={deleteOpen}
        count={selectedCount}
        onConfirm={() => deleteMutation.mutate(selectedIds)}
        onCancel={() => setDeleteOpen(false)}
        isPending={deleteMutation.isPending}
      />

      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Contacts</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {total > 0 ? `${total.toLocaleString()} contacts` : 'No contacts'}
          </p>
        </div>
        <Button onClick={() => setAddContactOpen(true)} className="gap-2">
          <UserPlus className="h-4 w-4" />
          Add Contact
        </Button>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-2 flex-wrap pb-2 border-b">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search contacts..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="w-64 pl-9"
          />
        </div>
        <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
          <SelectTrigger className="w-36 h-9">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            {STATUSES.map((s) => (
              <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          value={salesRepFilter}
          onChange={(e) => { setSalesRepFilter(e.target.value); setPage(1); }}
          placeholder="Filter by rep..."
          className="w-36 h-9"
        />
        <span className="text-xs text-muted-foreground ml-auto">
          {total > 0 ? `${startItem}–${endItem} of ${total.toLocaleString()}` : ''}
        </span>
      </div>

      {/* Bulk action bar — floats when rows selected */}
      {selectedCount > 0 && (
        <div className="flex items-center gap-2 px-3 py-2 bg-primary/5 border border-primary/20 rounded-lg">
          <span className="text-sm font-medium text-primary">{selectedCount} selected</span>
          <div className="h-4 w-px bg-border mx-1" />
          <Button variant="outline" size="sm" className="gap-1.5 h-7" onClick={() => setTagModalOpen(true)}>
            <Tag className="h-3 w-3" /> Tag
          </Button>
          <Button variant="outline" size="sm" className="h-7">Assign</Button>
          <Button variant="outline" size="sm" className="gap-1.5 h-7" onClick={() => exportToCSV(selectedContacts)}>
            <Download className="h-3 w-3" /> Export
          </Button>
          <Button
            variant="outline" size="sm"
            className="gap-1.5 h-7 text-destructive hover:text-destructive hover:bg-destructive/10 border-destructive/30"
            onClick={() => setDeleteOpen(true)}
          >
            <Trash2 className="h-3 w-3" /> Delete
          </Button>
          <Button
            variant="ghost" size="sm"
            className="h-7 w-7 p-0 ml-auto text-muted-foreground"
            onClick={() => setRowSelection({})}
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      )}

      {/* Table */}
      <div className="rounded-md border overflow-x-auto">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((hg) => (
              <TableRow key={hg.id} className="bg-muted/40 hover:bg-muted/40">
                {hg.headers.map((header) => {
                  const isStatus = header.column.id === 'status';
                  const isSelect = header.column.id === 'select';
                  return (
                    <TableHead
                      key={header.id}
                      className={cn(
                        header.column.getCanSort() ? 'cursor-pointer select-none' : '',
                        'whitespace-nowrap text-xs font-semibold uppercase tracking-wide text-muted-foreground',
                        isStatus && 'sticky right-0 z-10 bg-muted/40 border-l',
                        isSelect && 'sticky left-0 z-10 bg-muted/40',
                      )}
                      onClick={header.column.getToggleSortingHandler()}
                    >
                      <span className="inline-flex items-center gap-1">
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {header.column.getIsSorted() === 'asc' && <span className="text-primary">↑</span>}
                        {header.column.getIsSorted() === 'desc' && <span className="text-primary">↓</span>}
                      </span>
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 10 }).map((_, i) => (
                <TableRow key={i}>
                  {table.getVisibleLeafColumns().map((col) => (
                    <TableCell key={col.id}>
                      <div className="h-4 bg-muted rounded animate-pulse" style={{ width: `${50 + (i * 13 % 50)}%` }} />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : !table.getRowModel().rows.length ? (
              <TableRow>
                <TableCell colSpan={table.getVisibleLeafColumns().length} className="text-center py-16">
                  <p className="text-base font-medium text-muted-foreground">
                    {search ? 'No contacts match your search' : 'No contacts found'}
                  </p>
                  <p className="text-sm text-muted-foreground mt-1">
                    {search ? 'Try adjusting your filters' : 'Add a contact to get started'}
                  </p>
                </TableCell>
              </TableRow>
            ) : (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  className="cursor-pointer hover:bg-muted/30 transition-colors h-[52px]"
                  onClick={() => navigate({ to: '/contacts/$contactId', params: { contactId: row.original.id } })}
                  data-state={row.getIsSelected() ? 'selected' : undefined}
                >
                  {row.getVisibleCells().map((cell) => {
                    const isStatus = cell.column.id === 'status';
                    const isSelect = cell.column.id === 'select';
                    const isInteractive = ['select','status','next_step','sarson_rep','last_contacted_at'].includes(cell.column.id);
                    return (
                      <TableCell
                        key={cell.id}
                        className={cn(
                          'py-3',
                          isStatus && 'sticky right-0 z-10 bg-background border-l',
                          isSelect && 'sticky left-0 z-10 bg-background',
                          row.getIsSelected() && (isStatus || isSelect) && 'bg-muted',
                        )}
                        onClick={isInteractive ? (e: React.MouseEvent) => e.stopPropagation() : undefined}
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between pt-1">
        <span className="text-sm text-muted-foreground">
          {total > 0 ? `Page ${page} of ${totalPages}` : ''}
        </span>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            Previous
          </Button>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}

function cn(...classes: (string | boolean | undefined)[]) {
  return classes.filter(Boolean).join(' ');
}
