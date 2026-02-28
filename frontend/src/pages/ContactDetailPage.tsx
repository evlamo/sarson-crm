import { useState, useEffect, useRef } from 'react';
import { formatDate, formatTime } from '@/lib/formatDate';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useNavigate } from '@tanstack/react-router';
import { toast } from 'sonner';
import api from '@/lib/api';
import { copyToClipboard } from '@/lib/clipboard';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { ArrowLeft, Mail, Phone, MessageSquare, Calendar, FileText, CheckCircle, Linkedin, Globe, ExternalLink } from 'lucide-react';
import { RepAssignPopover } from '@/components/RepAssignPopover';
import { EditableField } from '@/components/EditableField';
import { CompanyCombobox } from '@/components/CompanyCombobox';

interface ContactDetail {
  id: string;
  first_name: string | null;
  middle_name: string | null;
  last_name: string | null;
  email: string | null;
  phone: string | null;
  title: string | null;
  company: string | null;
  company_name: string | null;
  company_id: string | null;
  status: string;
  sarson_rep: string | null;
  next_step: string | null;
  last_contacted_at: string | null;
  notes: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  linkedin_url: string | null;
  website: string | null;
  email_domain: string | null;
  source: string | null;
  lead_source: string | null;
  email_open_count: number;
  email_click_count: number;
  tags?: { id: string; name: string; color: string }[];
  created_at: string;
  updated_at: string;
}

interface Activity {
  id: string;
  activity_type: string;
  subject: string | null;
  body: string | null;
  performed_at: string;
  performed_by: string | null;
}

const ACTIVITY_ICONS: Record<string, typeof Mail> = {
  email: Mail,
  call: Phone,
  note: MessageSquare,
  meeting: Calendar,
  task: CheckCircle,
  document: FileText,
};

const TAG_COLORS = [
  'bg-blue-500', 'bg-green-500', 'bg-purple-500', 'bg-orange-500',
  'bg-pink-500', 'bg-teal-500', 'bg-indigo-500', 'bg-rose-500',
];

function getTagColorFromId(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = ((hash << 5) - hash) + id.charCodeAt(i);
    hash |= 0;
  }
  return TAG_COLORS[Math.abs(hash) % TAG_COLORS.length];
}

const STATUS_OPTIONS = [
  { value: 'hot', label: 'Hot' },
  { value: 'warm', label: 'Warm' },
  { value: 'prospect', label: 'Prospect' },
  { value: 'cold', label: 'Cold' },
  { value: 'poc', label: 'POC' },
  { value: 'active', label: 'Active' },
  { value: 'na', label: 'N/A' },
];

const STATUS_COLORS: Record<string, string> = {
  hot: 'bg-red-500',
  warm: 'bg-orange-500',
  prospect: 'bg-blue-500',
  cold: 'bg-gray-400',
  poc: 'bg-purple-500',
  active: 'bg-green-500',
  na: 'bg-gray-300',
};


function StatusDot({ status }: { status: string }) {
  const color = STATUS_COLORS[status] || 'bg-gray-300';
  return <span className={`inline-block w-2.5 h-2.5 rounded-full ${color} mr-2`} />;
}

function getInitials(first: string | null, last: string | null, email?: string | null): string {
  const f = (first || '').trim()[0] || '';
  const l = (last || '').trim()[0] || '';
  return (f + l).toUpperCase() || email?.charAt(0).toUpperCase() || '?';
}

function FieldRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-0.5 py-1">
      <span className="text-xs font-medium text-muted-foreground block">{label}</span>
      <div className="text-sm">{children}</div>
    </div>
  );
}

function InlineLastContactedDetail({ contact, onSave }: { contact: ContactDetail; onSave: (field: string, value: string) => Promise<void> }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const save = async () => {
    const current = contact.last_contacted_at ? contact.last_contacted_at.slice(0, 10) : '';
    if (draft !== current) {
      await onSave('last_contacted_at', draft);
    }
    setEditing(false);
  };

  const start = () => {
    const iso = contact.last_contacted_at ? contact.last_contacted_at.slice(0, 10) : '';
    setDraft(iso);
    setEditing(true);
    timerRef.current = setTimeout(() => inputRef.current?.focus(), 0);
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
        }}
        className="h-7 px-2 text-sm border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-primary"
      />
    );
  }

  const display = contact.last_contacted_at ? formatDate(contact.last_contacted_at) : null;
  return (
    <span
      onClick={start}
      className="text-sm cursor-pointer hover:text-primary transition-colors inline-flex items-center gap-1 group"
      title="Click to set date"
    >
      {display || <span className="text-muted-foreground italic">— <span className="text-xs opacity-0 group-hover:opacity-100 transition-opacity">set date</span></span>}
    </span>
  );
}

function InlineLeadSource({ value, onSave }: { value: string | null; onSave: (v: string) => Promise<void> }) {
  const [editing, setEditing] = useState(false);
  const [selected, setSelected] = useState('');
  const [customText, setCustomText] = useState('');
  const customInputRef = useRef<HTMLInputElement>(null);

  const INLINE_LEAD_SOURCE_OPTIONS = [
    { value: 'website', label: 'Website' },
    { value: 'referral', label: 'Referral' },
    { value: 'linkedin', label: 'LinkedIn' },
    { value: 'conference', label: 'Conference' },
    { value: 'cold_outreach', label: 'Cold Outreach' },
    { value: 'inbound', label: 'Inbound' },
    { value: 'import', label: 'Import' },
    { value: 'other', label: 'Other...' },
  ];

  const knownValues = INLINE_LEAD_SOURCE_OPTIONS.map(o => o.value);

  const start = () => {
    const isKnown = knownValues.includes(value || '');
    setSelected(isKnown ? (value || '') : (value ? 'other' : ''));
    setCustomText(isKnown ? '' : (value || ''));
    setEditing(true);
  };

  const save = async (finalValue: string) => {
    if (finalValue && finalValue !== value) {
      await onSave(finalValue);
    }
    setEditing(false);
  };

  const handleSelectChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const v = e.target.value;
    setSelected(v);
    if (v !== 'other' && v !== '') {
      save(v);
    } else if (v === 'other') {
      setTimeout(() => customInputRef.current?.focus(), 0);
    }
  };

  const displayLabel = () => {
    if (!value) return null;
    const opt = INLINE_LEAD_SOURCE_OPTIONS.find(o => o.value === value);
    return opt ? opt.label : value;
  };

  if (!editing) {
    return (
      <span
        onClick={start}
        className="text-sm cursor-pointer hover:text-primary transition-colors"
        title="Click to edit"
      >
        {displayLabel() || <span className="text-muted-foreground italic">—</span>}
      </span>
    );
  }

  return (
    <div className="flex flex-col gap-1">
      <select
        autoFocus
        value={selected}
        onChange={handleSelectChange}
        onKeyDown={(e) => { if (e.key === 'Escape') setEditing(false); }}
        className="h-7 px-2 text-sm border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-primary"
      >
        <option value="">— Select —</option>
        {INLINE_LEAD_SOURCE_OPTIONS.map(o => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      {selected === 'other' && (
        <input
          ref={customInputRef}
          type="text"
          value={customText}
          onChange={e => setCustomText(e.target.value)}
          onBlur={() => save(customText.trim() || 'other')}
          onKeyDown={(e) => {
            if (e.key === 'Enter') save(customText.trim() || 'other');
            if (e.key === 'Escape') setEditing(false);
          }}
          placeholder="Describe the source..."
          className="h-7 px-2 text-sm border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-primary"
        />
      )}
    </div>
  );
}

function TagManager({ contact, onUpdate, removeTagMutation: removeTagExt }: { contact: ContactDetail; onUpdate: () => void; removeTagMutation: { mutate: (tagId: string) => void; isPending: boolean } }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const queryClient = useQueryClient();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    if (open) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const { data: allTags } = useQuery({
    queryKey: ['all-tags'],
    queryFn: async () => {
      const res = await api.get('/tags');
      const tags = Array.isArray(res.data) ? res.data : (res.data.data || res.data.items || []);
      return tags as { id: string; name: string; color: string }[];
    },
    enabled: open,
    staleTime: 30_000,
  });

  const contactTagIds = new Set(contact.tags?.map(t => t.id) || []);
  const atMax = (contact.tags?.length || 0) >= 8;

  const addTag = useMutation({
    mutationFn: async (tagId: string) => {
      await api.post(`/contacts/${contact.id}/tags/by-id`, null, { params: { tag_id: tagId } });
    },
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['contact', contact.id] }); queryClient.invalidateQueries({ queryKey: ['contacts'] }); onUpdate(); },
    onError: () => toast.error('Failed to add tag'),
  });

  const removeTag = removeTagExt;

  const createAndAddTag = useMutation({
    mutationFn: async (name: string) => {
      const res = await api.post<{ id: string; name: string; color: string }>('/tags', { name: name.trim() });
      const newTagId = res.data.id;
      await api.post(`/contacts/${contact.id}/tags/by-id`, null, { params: { tag_id: newTagId } });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contact', contact.id] });
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
      queryClient.invalidateQueries({ queryKey: ['all-tags'] });
      setSearch('');
      toast.success('Tag created and added');
      onUpdate();
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : 'Failed to create tag';
      toast.error(msg);
    },
  });

  const isMutating = addTag.isPending || removeTag.isPending || createAndAddTag.isPending;

  const filtered = (allTags || []).filter(t =>
    !search || t.name.toLowerCase().includes(search.toLowerCase())
  );
  const exactMatch = (allTags || []).some(t => t.name.toLowerCase() === search.toLowerCase());

  return (
    <div ref={ref} className="relative inline-block shrink-0">
      <button
        type="button"
        aria-expanded={open}
        aria-haspopup="listbox"
        onClick={() => setOpen(o => !o)}
        className="inline-flex items-center gap-1 px-2 py-1 rounded-full border border-dashed border-muted-foreground/40 text-xs text-muted-foreground hover:border-primary hover:text-primary transition-colors"
      >
        <span>+</span> Tag
      </button>
      {open && (
        <div className="absolute top-8 left-0 z-[100] w-56 bg-card border rounded-lg shadow-lg p-2">
          <input
            autoFocus
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search or create tag..."
            className="w-full px-2 py-1.5 text-sm border rounded mb-2 bg-background focus:outline-none focus:ring-1 focus:ring-primary"
          />
          {atMax && <p className="text-xs text-muted-foreground text-center py-1">Max 8 tags reached</p>}
          <div className="max-h-48 overflow-y-auto space-y-0.5">
            {filtered.map(tag => {
              const isOn = contactTagIds.has(tag.id);
              return (
                <button
                  key={tag.id}
                  type="button"
                  disabled={isMutating}
                  onClick={() => {
                    if (!isOn && atMax) { toast.error('Maximum 8 tags per contact'); return; }
                    isOn ? removeTag.mutate(tag.id) : addTag.mutate(tag.id);
                  }}
                  className="w-full flex items-center gap-2 px-2 py-1.5 text-sm rounded hover:bg-muted transition-colors text-left disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <span
                    className="h-2.5 w-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: tag.color || '#6366f1' }}
                  />
                  <span className="flex-1 truncate">{tag.name}</span>
                  {isOn && <span className="text-primary text-xs">✓</span>}
                </button>
              );
            })}
            {search && !exactMatch && !atMax && (
              <button
                type="button"
                onClick={() => createAndAddTag.mutate(search.trim())}
                disabled={isMutating}
                className="w-full flex items-center gap-2 px-2 py-1.5 text-sm rounded hover:bg-muted transition-colors text-left text-primary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span>+</span> Create &ldquo;{search.trim()}&rdquo;
              </button>
            )}
            {!filtered.length && !search && (
              <p className="text-xs text-muted-foreground text-center py-2">No tags yet</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function ContactDetailPage() {
  const { contactId } = useParams({ strict: false }) as { contactId: string };
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [noteText, setNoteText] = useState('');

  const { data: contact, isLoading, isError } = useQuery({
    queryKey: ['contact', contactId],
    queryFn: async () => {
      const res = await api.get<ContactDetail>(`/contacts/${contactId}`);
      return res.data;
    },
  });

  useEffect(() => {
    if (contact) {
      const name = [contact.first_name, contact.last_name].filter(Boolean).join(' ') || 'Contact';
      document.title = `${name} — Sarson Funds CRM`;
    }
  }, [contact]);

  const { data: activities, isLoading: activitiesLoading } = useQuery({
    queryKey: ['contact-activities', contactId],
    queryFn: async () => {
      const res = await api.get<{ data: Activity[] }>(`/contacts/${contactId}/activities`);
      return res.data.data || [];
    },
  });

  const patchContact = async (data: Record<string, unknown>) => {
    await api.patch(`/contacts/${contactId}`, data);
    queryClient.invalidateQueries({ queryKey: ['contact', contactId] });
    queryClient.invalidateQueries({ queryKey: ['contacts'] });
  };

  const updateMutation = useMutation({
    mutationFn: async (data: Partial<ContactDetail>) => {
      await api.patch(`/contacts/${contactId}`, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contact', contactId] });
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail || 'Failed to update contact');
    },
  });

  const removeTagMutation = useMutation({
    mutationFn: async (tagId: string) => {
      await api.delete(`/contacts/${contactId}/tags/${tagId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contact', contactId] });
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
    },
    onError: () => toast.error('Failed to remove tag'),
  });

  const addNoteMutation = useMutation({
    mutationFn: async (body: string) => {
      await api.post(`/contacts/${contactId}/activities`, {
        activity_type: 'note',
        body,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contact-activities', contactId] });
      setNoteText('');
      toast.success('Note added');
    },
    onError: () => {
      toast.error('Failed to add note');
    },
  });

  const savePatch = async (field: string, value: string) => {
    try {
      await patchContact({ [field]: value || null });
      toast.success('Updated');
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail || 'Failed to update');
      throw err;
    }
  };

  // Loading skeleton
  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-4 w-16 bg-muted rounded" />
        <div className="h-8 w-48 bg-muted rounded" />
        <div className="h-4 w-32 bg-muted rounded" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="h-64 bg-muted rounded-lg" />
          <div className="lg:col-span-2 h-64 bg-muted rounded-lg" />
        </div>
      </div>
    );
  }

  if (isError || !contact) {
    return (
      <div className="flex flex-col items-center justify-center py-24">
        <p className="text-4xl font-bold text-muted-foreground mb-2">404</p>
        <p className="text-muted-foreground mb-4">Contact not found</p>
        <Button onClick={() => navigate({ to: '/contacts' })}>
          <ArrowLeft className="h-4 w-4 mr-2" /> Back to Contacts
        </Button>
      </div>
    );
  }

  const fullName = [contact.first_name, contact.last_name].filter(Boolean).join(' ') || 'Unnamed Contact';
  const companyDisplay = contact.company_name || contact.company;

  return (
    <div className="space-y-6">
      {/* ─── Hero Header ─── */}
      <div className="bg-card border rounded-lg p-6">
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-4">
            <Button variant="ghost" size="icon" className="-ml-2 mt-1" onClick={() => navigate({ to: '/contacts' })}>
              <ArrowLeft className="h-4 w-4" />
            </Button>
            {/* Avatar */}
            <div className="h-16 w-16 rounded-full bg-[#1e293b] text-white flex items-center justify-center text-xl font-bold shrink-0">
              {getInitials(contact.first_name, contact.last_name, contact.email)}
            </div>
            <div className="min-w-0">
              <h1 className="text-2xl font-bold leading-tight">{fullName}</h1>
              <p className="text-muted-foreground mt-0.5">
                {contact.title}
                {contact.title && companyDisplay ? ' at ' : ''}
                {companyDisplay && (
                  <button
                    className="text-primary hover:underline"
                    onClick={() => navigate({ to: '/companies' })}
                  >
                    {companyDisplay}
                  </button>
                )}
              </p>
              {/* Tags with × and TagManager — horizontal scroll, max 8 */}
              <div className="flex gap-1.5 mt-2 items-center overflow-x-auto pb-1 max-w-full" style={{ scrollbarWidth: 'thin' }}>
                {contact.tags?.map((tag) => (
                  <span
                    key={tag.id}
                    className="inline-flex items-center gap-1 text-white text-xs px-2 py-0.5 rounded-full shrink-0"
                    style={{ backgroundColor: tag.color || '#6366f1' }}
                  >
                    {tag.name}
                    <button
                      type="button"
                      onClick={() => removeTagMutation.mutate(tag.id)}
                      className="ml-0.5 hover:opacity-70 transition-opacity leading-none"
                      aria-label={`Remove ${tag.name}`}
                    >×</button>
                  </span>
                ))}
                <TagManager contact={contact} onUpdate={() => queryClient.invalidateQueries({ queryKey: ['contact', contactId] })} removeTagMutation={removeTagMutation} />
              </div>
              {/* Quick-action chips */}
              <div className="flex items-center gap-2 mt-3 flex-wrap">
                {contact.email && (
                  <button
                    type="button"
                    onClick={() => { copyToClipboard(contact.email!); toast.success('Email copied!'); }}
                    className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-muted text-sm hover:bg-muted/80 transition-colors"
                    title="Click to copy email"
                  >
                    <Mail className="h-3.5 w-3.5" />
                    {contact.email}
                  </button>
                )}
                {contact.phone && (
                  <button
                    type="button"
                    onClick={() => { copyToClipboard(contact.phone!); toast.success('Phone copied!'); }}
                    className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-muted text-sm hover:bg-muted/80 transition-colors"
                    title="Click to copy phone"
                  >
                    <Phone className="h-3.5 w-3.5" />
                    {contact.phone}
                  </button>
                )}
                {contact.linkedin_url && (
                  <a href={contact.linkedin_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center justify-center h-8 w-8 rounded-full bg-muted hover:bg-muted/80 transition-colors">
                    <Linkedin className="h-4 w-4" />
                  </a>
                )}
                {contact.website && (
                  <a href={contact.website} target="_blank" rel="noopener noreferrer" className="inline-flex items-center justify-center h-8 w-8 rounded-full bg-muted hover:bg-muted/80 transition-colors">
                    <Globe className="h-4 w-4" />
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ─── Two-Column Layout ─── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ─── Left Column (1/3) ─── */}
        <div className="space-y-6 lg:col-span-1">
          {/* Card 1: CRM */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-widest">CRM</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <FieldRow label="Status">
                <div className="flex items-center">
                  <StatusDot status={contact.status} />
                  <EditableField
                    value={contact.status}
                    type="select"
                    options={STATUS_OPTIONS}
                    onSave={(v) => savePatch('status', v)}
                  />
                </div>
              </FieldRow>
              <FieldRow label="Sales Rep">
                <RepAssignPopover
                  contactId={contact.id}
                  currentRep={contact.sarson_rep}
                  variant="detail"
                />
              </FieldRow>
              <FieldRow label="Lead Source">
                <InlineLeadSource
                  value={contact.source || contact.lead_source}
                  onSave={(v) => savePatch('source', v)}
                />
              </FieldRow>
              <FieldRow label="Last Contacted">
                <InlineLastContactedDetail contact={contact} onSave={savePatch} />
              </FieldRow>
              {(contact.email_open_count > 0 || contact.email_click_count > 0) && (
                <FieldRow label="Email Stats">
                  <span className="text-xs space-x-2">
                    {contact.email_open_count > 0 && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 text-xs">{contact.email_open_count} opens</span>
                    )}
                    {contact.email_click_count > 0 && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-green-50 text-green-700 text-xs">{contact.email_click_count} clicks</span>
                    )}
                  </span>
                </FieldRow>
              )}
            </CardContent>
          </Card>

          {/* Card 2: Contact Info */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-widest">Contact Info</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <FieldRow label="First Name">
                <EditableField value={contact.first_name} onSave={(v) => savePatch('first_name', v)} placeholder="—" />
              </FieldRow>
              <FieldRow label="Last Name">
                <EditableField value={contact.last_name} onSave={(v) => savePatch('last_name', v)} placeholder="—" />
              </FieldRow>
              {contact.middle_name && (
                <FieldRow label="Middle Name">
                  <EditableField value={contact.middle_name} onSave={(v) => savePatch('middle_name', v)} placeholder="—" />
                </FieldRow>
              )}
              <FieldRow label="Email">
                <div className="flex items-center gap-2">
                  {contact.email ? (
                    <button
                      type="button"
                      onClick={() => { copyToClipboard(contact.email!); toast.success('Email copied!'); }}
                      className="text-sm hover:text-primary transition-colors text-left break-all"
                      title="Click to copy"
                    >
                      {contact.email}
                    </button>
                  ) : (
                    <span className="text-muted-foreground text-sm">—</span>
                  )}
                  <EditableField value={contact.email} type="email" onSave={(v) => savePatch('email', v)} placeholder="—" showPencilOnly />
                </div>
              </FieldRow>
              <FieldRow label="Phone">
                <div className="flex items-center gap-2">
                  {contact.phone ? (
                    <button
                      type="button"
                      onClick={() => { copyToClipboard(contact.phone!); toast.success('Phone copied!'); }}
                      className="text-sm hover:text-primary transition-colors text-left break-all"
                      title="Click to copy"
                    >
                      {contact.phone}
                    </button>
                  ) : (
                    <span className="text-muted-foreground text-sm">—</span>
                  )}
                  <EditableField value={contact.phone} type="tel" onSave={(v) => savePatch('phone', v)} placeholder="—" hint="+1234567890" showPencilOnly />
                </div>
              </FieldRow>
              <FieldRow label="Title">
                <EditableField value={contact.title} onSave={(v) => savePatch('title', v)} placeholder="—" />
              </FieldRow>
              <FieldRow label="Company">
                <div className="flex items-center gap-2">
                  {(contact.company_name || contact.company) && (
                    <button
                      type="button"
                      onClick={() => navigate({ to: '/companies' })}
                      className="text-sm text-primary hover:underline text-left truncate"
                      title="View company"
                    >
                      {contact.company_name || contact.company}
                    </button>
                  )}
                  <CompanyCombobox
                    companyName={contact.company_name || contact.company}
                    companyId={contact.company_id}
                    onSave={async (name, selectedCompanyId) => {
                      const payload: Record<string, unknown> = { company: name };
                      if (selectedCompanyId) payload.company_id = selectedCompanyId;
                      await patchContact(payload);
                      queryClient.invalidateQueries({ queryKey: ['contact', contactId] });
                      toast.success('Company updated');
                    }}
                    onNavigate={() => navigate({ to: '/companies' })}
                    showPencilOnly={!!(contact.company_name || contact.company)}
                  />
                </div>
              </FieldRow>
              <FieldRow label="City">
                <EditableField value={contact.city} onSave={(v) => savePatch('city', v)} placeholder="—" />
              </FieldRow>
              <FieldRow label="State">
                <EditableField value={contact.state} onSave={(v) => savePatch('state', v)} placeholder="—" />
              </FieldRow>
              <FieldRow label="Country">
                <EditableField value={contact.country} onSave={(v) => savePatch('country', v)} placeholder="—" />
              </FieldRow>
            </CardContent>
          </Card>

          {/* Card 3: Online */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-widest">Online</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <FieldRow label="LinkedIn">
                <div className="flex items-center gap-1 min-w-0">
                  <EditableField
                    value={contact.linkedin_url}
                    type="url"
                    onSave={(v) => savePatch('linkedin_url', v)}
                    placeholder="—"
                    linkHref={contact.linkedin_url || undefined}
                  />
                  {contact.linkedin_url && (
                    <a href={contact.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-muted-foreground hover:text-primary shrink-0">
                      <Linkedin className="h-3.5 w-3.5" />
                    </a>
                  )}
                </div>
              </FieldRow>
              <FieldRow label="Website">
                <div className="flex items-center gap-1 min-w-0">
                  <EditableField
                    value={contact.website}
                    type="url"
                    onSave={(v) => savePatch('website', v)}
                    placeholder="—"
                    linkHref={contact.website || undefined}
                  />
                  {contact.website && (
                    <a href={contact.website} target="_blank" rel="noopener noreferrer" className="text-muted-foreground hover:text-primary shrink-0">
                      <Globe className="h-3.5 w-3.5" />
                    </a>
                  )}
                </div>
              </FieldRow>
            </CardContent>
          </Card>
        </div>

        {/* ─── Right Column (2/3) ─── */}
        <div className="lg:col-span-2 space-y-6">
          {/* Notes & Activity */}
          <Card className="min-h-[400px] flex flex-col">
            <CardHeader>
              <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-widest">Notes & Activity</CardTitle>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col">
              <div className="flex gap-2 mb-4">
                <Input
                  placeholder="Write a note... (Enter to save)"
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && noteText.trim()) {
                      addNoteMutation.mutate(noteText.trim());
                    }
                  }}
                />
                <Button
                  size="sm"
                  disabled={!noteText.trim() || addNoteMutation.isPending}
                  onClick={() => addNoteMutation.mutate(noteText.trim())}
                >
                  {addNoteMutation.isPending ? 'Saving...' : 'Add'}
                </Button>
              </div>

              <Separator />

              <div className="space-y-3 mt-4 flex-1 overflow-y-auto">
                {activitiesLoading ? (
                  <div className="space-y-3">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="flex gap-3">
                        <div className="h-7 w-7 rounded-full bg-muted animate-pulse shrink-0" />
                        <div className="flex-1 space-y-2">
                          <div className="h-3 bg-muted rounded animate-pulse w-1/3" />
                          <div className="h-4 bg-muted rounded animate-pulse w-2/3" />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : !activities?.length ? (
                  <div className="text-center py-8">
                    <MessageSquare className="h-8 w-8 mx-auto text-muted-foreground/40 mb-2" />
                    <p className="text-sm text-muted-foreground">No notes yet</p>
                    <p className="text-xs text-muted-foreground mt-1">Add a note to start tracking progress</p>
                  </div>
                ) : (
                  activities.map((activity) => {
                    const Icon = ACTIVITY_ICONS[activity.activity_type] || FileText;
                    const isNote = activity.activity_type === 'note';
                    const dateStr = activity.performed_at ? formatDate(activity.performed_at) : '';
                    const timeStr = activity.performed_at ? formatTime(activity.performed_at) : '';

                    return (
                      <div key={activity.id} className="flex gap-3 group">
                        <div className={`mt-1 shrink-0 h-7 w-7 rounded-full flex items-center justify-center ${isNote ? 'bg-primary/10' : 'bg-muted'}`}>
                          <Icon className={`h-3.5 w-3.5 ${isNote ? 'text-primary' : 'text-muted-foreground'}`} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-baseline gap-2 flex-wrap">
                            {!isNote && (
                              <span className="text-xs font-semibold capitalize text-muted-foreground">{activity.activity_type}</span>
                            )}
                            <span className="text-xs text-muted-foreground">{dateStr}</span>
                            <span className="text-xs text-muted-foreground/60">{timeStr}</span>
                          </div>
                          {activity.subject && <p className="text-sm font-medium mt-0.5">{activity.subject}</p>}
                          {activity.body && <p className="text-sm mt-0.5 whitespace-pre-wrap leading-relaxed">{activity.body}</p>}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </CardContent>
          </Card>

          {/* Next Step */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-widest">Next Step</CardTitle>
            </CardHeader>
            <CardContent>
              <EditableField
                value={contact.next_step}
                type="textarea"
                onSave={(v) => savePatch('next_step', v)}
                placeholder="Add next step..."
                className="w-full"
              />
            </CardContent>
          </Card>

          {/* Background Notes */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-widest">Background Notes</CardTitle>
            </CardHeader>
            <CardContent>
              <EditableField
                value={contact.notes}
                type="textarea"
                onSave={(v) => savePatch('notes', v)}
                placeholder="Add background notes..."
                className="w-full"
              />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
