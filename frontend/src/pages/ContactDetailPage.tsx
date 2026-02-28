import { useState, useEffect, useRef } from 'react';
import { formatDate, formatTime } from '@/lib/formatDate';
import { STATUSES, getStatus } from '@/lib/statuses';
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

function getTagColorFromId(id: string): string {
  const COLORS = ['#3b82f6','#22c55e','#a855f7','#f97316','#ec4899','#14b8a6','#6366f1','#f43f5e'];
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = ((hash << 5) - hash) + id.charCodeAt(i);
    hash |= 0;
  }
  return COLORS[Math.abs(hash) % COLORS.length];
}

const STATUS_OPTIONS = STATUSES.map(s => ({ value: s.value, label: s.label }));

function StatusDot({ status }: { status: string }) {
  const { dot } = getStatus(status);
  return <span className={`inline-block w-2.5 h-2.5 rounded-full ${dot} mr-2`} />;
}

function StatusBadge({ status }: { status: string }) {
  const { label, badge } = getStatus(status);
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-0.5 rounded-full border ${badge}`}>
      {label}
    </span>
  );
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

function TagInput({
  contact,
  onUpdate,
  onRemoveTag,
}: {
  contact: ContactDetail;
  onUpdate: () => void;
  onRemoveTag: (tagId: string) => void;
}) {
  const [value, setValue] = useState('');
  const [focused, setFocused] = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  const { data: allTags = [] } = useQuery({
    queryKey: ['all-tags'],
    queryFn: async () => {
      const res = await api.get<{ id: string; name: string; color: string }[]>('/tags');
      return Array.isArray(res.data) ? res.data : [];
    },
    staleTime: 30_000,
  });

  const contactTagIds = new Set(contact.tags?.map(t => t.id) ?? []);
  const atMax = (contact.tags?.length ?? 0) >= 8;

  const suggestions = value.trim()
    ? allTags.filter(t =>
        t.name.toLowerCase().includes(value.toLowerCase()) &&
        !contactTagIds.has(t.id)
      ).slice(0, 6)
    : [];

  const exactMatch = allTags.find(
    t => t.name.toLowerCase() === value.trim().toLowerCase()
  );
  const showCreate = value.trim() && !exactMatch && !atMax;
  const showDropdown = focused && value.trim() && (suggestions.length > 0 || showCreate);
  const totalOptions = suggestions.length + (showCreate ? 1 : 0);

  useEffect(() => { setActiveIdx(0); }, [value]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['contact', contact.id] });
    queryClient.invalidateQueries({ queryKey: ['contacts'] });
    onUpdate();
  };

  const addByIdMutation = useMutation({
    mutationFn: (tagId: string) =>
      api.post(`/contacts/${contact.id}/tags/by-id`, null, { params: { tag_id: tagId } }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['tags'] }); invalidate(); setValue(''); toast.success('Tag added'); },
    onError: () => toast.error('Failed to add tag'),
  });

  const createAndAddMutation = useMutation({
    mutationFn: (name: string) =>
      api.post(`/contacts/${contact.id}/tags`, { name: name.trim() }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['all-tags'] });
      queryClient.invalidateQueries({ queryKey: ['tags'] });
      invalidate();
      setValue('');
      toast.success('Tag added');
    },
    onError: () => toast.error('Failed to add tag'),
  });

  const isMutating = addByIdMutation.isPending || createAndAddMutation.isPending;

  const commitValue = (text: string) => {
    if (!text.trim() || isMutating) return;
    if (atMax) { toast.error('Max 8 tags per contact'); return; }
    const match = allTags.find(t => t.name.toLowerCase() === text.trim().toLowerCase());
    if (match) {
      if (contactTagIds.has(match.id)) { setValue(''); return; }
      addByIdMutation.mutate(match.id);
    } else {
      createAndAddMutation.mutate(text.trim());
    }
  };

  const commitSuggestion = (tag: { id: string; name: string }) => {
    if (isMutating || atMax) return;
    if (contactTagIds.has(tag.id)) { setValue(''); return; }
    addByIdMutation.mutate(tag.id);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (showDropdown && suggestions.length > 0 && activeIdx < suggestions.length) {
        commitSuggestion(suggestions[activeIdx]);
      } else if (showDropdown && showCreate && activeIdx === suggestions.length) {
        createAndAddMutation.mutate(value.trim());
      } else {
        commitValue(value);
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx(i => Math.min(i + 1, totalOptions - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx(i => Math.max(i - 1, 0));
    } else if (e.key === 'Escape') {
      setValue('');
      setFocused(false);
      inputRef.current?.blur();
    } else if (e.key === 'Backspace' && !value && contact.tags?.length) {
      const lastTag = contact.tags[contact.tags.length - 1];
      onRemoveTag(lastTag.id);
    }
  };

  return (
    <div className="relative">
      {/* Tags row — horizontal, no wrap, + Tag button on the right */}
      <div className="flex items-center gap-1.5 overflow-x-auto" style={{ scrollbarWidth: 'none' }}>
        {/* Tag chips */}
        {contact.tags?.map(tag => (
          <span
            key={tag.id}
            className="inline-flex items-center gap-1 text-white text-xs px-2.5 py-1 rounded-full font-medium shrink-0"
            style={{ backgroundColor: tag.color || getTagColorFromId(tag.id) }}
          >
            {tag.name}
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onRemoveTag(tag.id); }}
              className="opacity-70 hover:opacity-100 transition-opacity leading-none ml-0.5"
              aria-label={`Remove ${tag.name}`}
            >
              ×
            </button>
          </span>
        ))}

        {/* + Tag button — always on the right, looks like a real button */}
        {!atMax && (
          <button
            type="button"
            onClick={() => { setFocused(true); setTimeout(() => inputRef.current?.focus(), 0); }}
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border shrink-0 transition-all ${
              focused
                ? 'border-primary text-primary bg-primary/5'
                : 'border-border text-muted-foreground bg-muted/50 hover:border-primary/50 hover:text-primary hover:bg-primary/5'
            }`}
          >
            {isMutating ? (
              <span className="animate-pulse">···</span>
            ) : (
              <>+ Tag</>
            )}
          </button>
        )}
        {atMax && (
          <span className="text-xs text-muted-foreground shrink-0 ml-1">Max 8</span>
        )}
      </div>

      {/* Hidden input — focused when + Tag is clicked */}
      {!atMax && (
        <div className={`mt-1.5 transition-all ${focused ? 'block' : 'hidden'}`}>
          <input
            ref={inputRef}
            type="text"
            value={value}
            onChange={e => setValue(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setTimeout(() => setFocused(false), 200)}
            onKeyDown={handleKeyDown}
            placeholder="Search or create tag..."
            className="w-full h-8 px-3 text-sm rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
            disabled={isMutating}
          />
        </div>
      )}

      {showDropdown && (
        <div className="absolute top-full left-0 mt-1 z-[100] w-56 bg-popover border border-border rounded-xl shadow-xl py-1 overflow-hidden">
          {suggestions.map((tag, i) => (
            <button
              key={tag.id}
              type="button"
              onMouseDown={(e) => { e.preventDefault(); commitSuggestion(tag); }}
              className={`w-full flex items-center gap-2 px-3 py-2 text-sm text-left transition-colors ${
                i === activeIdx ? 'bg-muted' : 'hover:bg-muted/60'
              }`}
            >
              <span
                className="h-2 w-2 rounded-full shrink-0"
                style={{ backgroundColor: tag.color || '#6366f1' }}
              />
              <span className="flex-1 truncate">{tag.name}</span>
              <span className="text-xs text-muted-foreground">↵</span>
            </button>
          ))}
          {showCreate && (
            <button
              type="button"
              onMouseDown={(e) => { e.preventDefault(); createAndAddMutation.mutate(value.trim()); }}
              className={`w-full flex items-center gap-2 px-3 py-2 text-sm text-left transition-colors text-primary ${
                activeIdx === suggestions.length ? 'bg-muted' : 'hover:bg-muted/60'
              }`}
            >
              <span className="font-semibold">+</span>
              <span>Create "<strong>{value.trim()}</strong>"</span>
              <span className="ml-auto text-xs text-muted-foreground">↵</span>
            </button>
          )}
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
      queryClient.invalidateQueries({ queryKey: ['tags'] });
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
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-2xl font-bold leading-tight">{fullName}</h1>
                <StatusBadge status={contact.status} />
              </div>
              <p className="text-muted-foreground mt-0.5">
                {contact.title}
                {contact.title && companyDisplay ? ' at ' : ''}
                {companyDisplay && (
                  <button
                    className="text-primary hover:underline"
                    onClick={() => navigate({ to: '/companies', search: { q: companyDisplay, ...(contact.company_id ? { openId: contact.company_id } : {}) } })}
                  >
                    {companyDisplay}
                  </button>
                )}
              </p>
              {/* Tags — inline chip input */}
              <div className="mt-2 max-w-lg">
                <TagInput
                  contact={contact}
                  onUpdate={() => queryClient.invalidateQueries({ queryKey: ['contact', contactId] })}
                  onRemoveTag={(tagId) => removeTagMutation.mutate(tagId)}
                />
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
                      onClick={() => navigate({ to: '/companies', search: { ...(contact.company_id ? { openId: contact.company_id } : { q: contact.company_name || contact.company || '' }) } })}
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
