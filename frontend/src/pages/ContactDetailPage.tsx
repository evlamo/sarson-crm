import { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useNavigate } from '@tanstack/react-router';
import { toast } from 'sonner';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { ArrowLeft, Mail, Phone, MessageSquare, Calendar, FileText, CheckCircle, Pencil, Check, X } from 'lucide-react';

interface ContactDetail {
  id: string;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  phone: string | null;
  title: string | null;
  company: string | null;
  status: string;
  contacted: boolean;
  sarson_rep: string | null;
  next_step: string | null;
  last_contacted_at: string | null;
  notes: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  linkedin_url: string | null;
  website: string | null;
  source: string | null;
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

export default function ContactDetailPage() {
  const { contactId } = useParams({ strict: false }) as { contactId: string };
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [noteText, setNoteText] = useState('');
  const [editingNextStep, setEditingNextStep] = useState(false);
  const [nextStepDraft, setNextStepDraft] = useState('');
  const nextStepRef = useRef<HTMLInputElement>(null);
  const [editingSalesRep, setEditingSalesRep] = useState(false);
  const [salesRepDraft, setSalesRepDraft] = useState('');
  const salesRepRef = useRef<HTMLInputElement>(null);

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

  const { data: activities } = useQuery({
    queryKey: ['contact-activities', contactId],
    queryFn: async () => {
      const res = await api.get<{ data: Activity[] }>(`/contacts/${contactId}/activities`);
      return res.data.data || [];
    },
  });

  const updateMutation = useMutation({
    mutationFn: async (data: Partial<ContactDetail>) => {
      await api.patch(`/contacts/${contactId}`, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contact', contactId] });
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
      setEditing(false);
      toast.success('Contact updated');
    },
    onError: () => {
      toast.error('Failed to update contact');
    },
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

  const nextStepMutation = useMutation({
    mutationFn: async (value: string) => {
      await api.patch(`/contacts/${contactId}`, { next_step: value || null });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contact', contactId] });
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
      setEditingNextStep(false);
      toast.success('Next step updated');
    },
    onError: () => toast.error('Failed to update next step'),
  });

  const startEditingNextStep = () => {
    setNextStepDraft(contact?.next_step || '');
    setEditingNextStep(true);
    setTimeout(() => nextStepRef.current?.focus(), 0);
  };

  const saveNextStep = () => {
    if (nextStepDraft !== (contact?.next_step || '')) {
      nextStepMutation.mutate(nextStepDraft);
    } else {
      setEditingNextStep(false);
    }
  };

  const salesRepMutation = useMutation({
    mutationFn: async (value: string) => {
      await api.patch(`/contacts/${contactId}`, { sarson_rep: value || null });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contact', contactId] });
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
      setEditingSalesRep(false);
      toast.success('Sales rep updated');
    },
    onError: () => toast.error('Failed to update sales rep'),
  });

  const startEditingSalesRep = () => {
    setSalesRepDraft(contact?.sarson_rep || '');
    setEditingSalesRep(true);
    setTimeout(() => salesRepRef.current?.focus(), 0);
  };

  const saveSalesRep = () => {
    if (salesRepDraft !== (contact?.sarson_rep || '')) salesRepMutation.mutate(salesRepDraft);
    else setEditingSalesRep(false);
  };

  const toggleContacted = () => {
    if (contact) {
      updateMutation.mutate({ contacted: !contact.contacted });
    }
  };

  const [editForm, setEditForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    title: '',
    company: '',
    next_step: '',
    notes: '',
    linkedin_url: '',
    website: '',
    city: '',
    state: '',
    country: '',
    source: '',
  });

  // Background Notes inline editing
  const [editingNotes, setEditingNotes] = useState(false);
  const [notesDraft, setNotesDraft] = useState('');
  const notesRef = useRef<HTMLTextAreaElement>(null);

  const notesMutation = useMutation({
    mutationFn: async (value: string) => {
      await api.patch(`/contacts/${contactId}`, { notes: value || null });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contact', contactId] });
      setEditingNotes(false);
      toast.success('Background notes updated');
    },
    onError: () => toast.error('Failed to update notes'),
  });

  const startEditingNotes = () => {
    setNotesDraft(contact?.notes || '');
    setEditingNotes(true);
    setTimeout(() => notesRef.current?.focus(), 0);
  };

  const saveNotes = () => {
    if (notesDraft !== (contact?.notes || '')) notesMutation.mutate(notesDraft);
    else setEditingNotes(false);
  };

  const contactId_str = contact?.id;
  const [lastSyncedId, setLastSyncedId] = useState<string | null>(null);
  if (contact && contactId_str !== lastSyncedId) {
    setLastSyncedId(contactId_str!);
    setEditForm({
      first_name: contact.first_name || '',
      last_name: contact.last_name || '',
      email: contact.email || '',
      phone: contact.phone || '',
      title: contact.title || '',
      company: contact.company || '',
      next_step: contact.next_step || '',
      notes: contact.notes || '',
      linkedin_url: contact.linkedin_url || '',
      website: contact.website || '',
      city: contact.city || '',
      state: contact.state || '',
      country: contact.country || '',
      source: contact.source || '',
    });
  }

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

  // 404 / Error state
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Button variant="ghost" size="sm" className="mb-1 -ml-3" onClick={() => navigate({ to: '/contacts' })}>
            <ArrowLeft className="h-4 w-4 mr-1" /> Back to Contacts
          </Button>
          <h1 className="text-2xl font-bold">{fullName}</h1>
          <p className="text-muted-foreground">
            {contact.title}{contact.title && contact.company ? ' at ' : ''}{contact.company}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant={contact.contacted ? 'default' : 'outline'}
            size="sm"
            onClick={toggleContacted}
          >
            {contact.contacted ? '✓ Contacted' : 'Mark Contacted'}
          </Button>
          <Button variant="outline" size="sm" onClick={() => setEditing(!editing)}>
            {editing ? 'Cancel' : 'Edit'}
          </Button>
        </div>
      </div>

      {/* Tags */}
      {contact.tags && contact.tags.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {contact.tags.map((tag, i) => (
            <Badge
              key={tag.id}
              className={`${tag.color ? '' : TAG_COLORS[i % TAG_COLORS.length]} text-white`}
              style={tag.color ? { backgroundColor: tag.color, color: '#fff' } : undefined}
            >
              {tag.name}
            </Badge>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Contact Info / Edit Form */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Contact Info</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {editing ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  updateMutation.mutate(editForm);
                }}
                className="space-y-3"
              >
                <div>
                  <Label>First Name</Label>
                  <Input value={editForm.first_name} onChange={(e) => setEditForm({ ...editForm, first_name: e.target.value })} />
                </div>
                <div>
                  <Label>Last Name</Label>
                  <Input value={editForm.last_name} onChange={(e) => setEditForm({ ...editForm, last_name: e.target.value })} />
                </div>
                <div>
                  <Label>Email</Label>
                  <Input value={editForm.email} onChange={(e) => setEditForm({ ...editForm, email: e.target.value })} />
                </div>
                <div>
                  <Label>Phone</Label>
                  <Input value={editForm.phone} onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })} />
                </div>
                <div>
                  <Label>Title</Label>
                  <Input value={editForm.title} onChange={(e) => setEditForm({ ...editForm, title: e.target.value })} />
                </div>
                <div>
                  <Label>Company</Label>
                  <Input value={editForm.company} onChange={(e) => setEditForm({ ...editForm, company: e.target.value })} />
                </div>
                <div>
                  <Label>Next Step</Label>
                  <Input value={editForm.next_step} onChange={(e) => setEditForm({ ...editForm, next_step: e.target.value })} />
                </div>
                <div>
                  <Label>LinkedIn URL</Label>
                  <Input value={editForm.linkedin_url} onChange={(e) => setEditForm({ ...editForm, linkedin_url: e.target.value })} placeholder="https://linkedin.com/in/..." />
                </div>
                <div>
                  <Label>Website</Label>
                  <Input value={editForm.website} onChange={(e) => setEditForm({ ...editForm, website: e.target.value })} placeholder="https://..." />
                </div>
                <div>
                  <Label>City</Label>
                  <Input value={editForm.city} onChange={(e) => setEditForm({ ...editForm, city: e.target.value })} />
                </div>
                <div>
                  <Label>State</Label>
                  <Input value={editForm.state} onChange={(e) => setEditForm({ ...editForm, state: e.target.value })} />
                </div>
                <div>
                  <Label>Country</Label>
                  <Input value={editForm.country} onChange={(e) => setEditForm({ ...editForm, country: e.target.value })} />
                </div>
                <div>
                  <Label>Source</Label>
                  <Input value={editForm.source} onChange={(e) => setEditForm({ ...editForm, source: e.target.value })} />
                </div>
                <div className="flex gap-2">
                  <Button type="submit" size="sm" disabled={updateMutation.isPending}>
                    {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
                  </Button>
                  <Button type="button" variant="outline" size="sm" onClick={() => setEditing(false)}>
                    Cancel
                  </Button>
                </div>
              </form>
            ) : (
              <div className="space-y-3 text-sm">
                <InfoRow label="Email" value={contact.email} />
                <InfoRow label="Phone" value={contact.phone} />
                <InfoRow label="Title" value={contact.title} />
                <InfoRow label="Company" value={contact.company} />
                <InfoRow label="Status" value={contact.status} />
                {contact.linkedin_url && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">LinkedIn</span>
                    <a href={contact.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline truncate max-w-[60%]">
                      {contact.linkedin_url.replace(/^https?:\/\/(www\.)?linkedin\.com\/in\//, '').replace(/\/$/, '') || 'Profile'}
                    </a>
                  </div>
                )}
                {contact.website && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Website</span>
                    <a href={contact.website} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline truncate max-w-[60%]">
                      {contact.website.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '')}
                    </a>
                  </div>
                )}
                <InfoRow label="Location" value={[contact.city, contact.state, contact.country].filter(Boolean).join(', ')} />
                {contact.source && <InfoRow label="Source" value={contact.source} />}
                {contact.last_contacted_at && (
                  <InfoRow label="Last Contacted" value={new Date(contact.last_contacted_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })} />
                )}
                {(contact.email_open_count > 0 || contact.email_click_count > 0) && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Email Stats</span>
                    <span className="text-xs space-x-2">
                      {contact.email_open_count > 0 && <span>{contact.email_open_count} opens</span>}
                      {contact.email_click_count > 0 && <span>{contact.email_click_count} clicks</span>}
                    </span>
                  </div>
                )}
                {/* Sales Rep — inline editable */}
                <div className="flex justify-between items-center min-h-[24px]">
                  <span className="text-muted-foreground shrink-0">Sales Rep</span>
                  {editingSalesRep ? (
                    <div className="flex items-center gap-1 flex-1 ml-2">
                      <input
                        ref={salesRepRef}
                        value={salesRepDraft}
                        onChange={(e) => setSalesRepDraft(e.target.value)}
                        onBlur={saveSalesRep}
                        onKeyDown={(e) => { if (e.key === 'Enter') saveSalesRep(); if (e.key === 'Escape') setEditingSalesRep(false); }}
                        placeholder="Assign rep..."
                        className="flex-1 h-6 px-2 text-xs border rounded bg-background focus:outline-none focus:ring-1 focus:ring-primary text-right"
                      />
                      <button onClick={() => setEditingSalesRep(false)} className="text-muted-foreground hover:text-foreground"><X className="h-3 w-3" /></button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1 group cursor-pointer" onClick={startEditingSalesRep}>
                      <span className={contact.sarson_rep ? '' : 'text-muted-foreground italic'}>{contact.sarson_rep || '—'}</span>
                      <Pencil className="h-3 w-3 opacity-0 group-hover:opacity-50 transition-opacity" />
                    </div>
                  )}
                </div>
                <Separator />
                {/* Next Step — inline editable, nested at bottom */}
                <div className="flex justify-between items-center min-h-[24px]">
                  <span className="text-muted-foreground shrink-0">Next Step</span>
                  {editingNextStep ? (
                    <div className="flex items-center gap-1 flex-1 ml-2">
                      <input
                        ref={nextStepRef}
                        value={nextStepDraft}
                        onChange={(e) => setNextStepDraft(e.target.value)}
                        onBlur={saveNextStep}
                        onKeyDown={(e) => { if (e.key === 'Enter') saveNextStep(); if (e.key === 'Escape') setEditingNextStep(false); }}
                        placeholder="Add next step..."
                        className="flex-1 h-6 px-2 text-xs border rounded bg-background focus:outline-none focus:ring-1 focus:ring-primary text-right"
                      />
                      <button onClick={() => setEditingNextStep(false)} className="text-muted-foreground hover:text-foreground"><X className="h-3 w-3" /></button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1 group cursor-pointer max-w-[60%]" onClick={startEditingNextStep}>
                      <span className={`text-right truncate ${contact.next_step ? 'font-medium' : 'text-muted-foreground italic'}`}>{contact.next_step || '—'}</span>
                      <Pencil className="h-3 w-3 shrink-0 opacity-0 group-hover:opacity-50 transition-opacity" />
                    </div>
                  )}
                </div>

              </div>
            )}
          </CardContent>
        </Card>

        {/* Activity Timeline */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Notes & Activity</CardTitle>
          </CardHeader>
          <CardContent>
            {/* Add Note */}
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

            {/* Timeline */}
            <div className="space-y-3 mt-4">
              {!activities?.length ? (
                <div className="text-center py-8">
                  <MessageSquare className="h-8 w-8 mx-auto text-muted-foreground/40 mb-2" />
                  <p className="text-sm text-muted-foreground">No notes yet</p>
                  <p className="text-xs text-muted-foreground mt-1">Add a note to start tracking progress</p>
                </div>
              ) : (
                activities.map((activity) => {
                  const Icon = ACTIVITY_ICONS[activity.activity_type] || FileText;
                  const isNote = activity.activity_type === 'note';
                  const dt = activity.performed_at ? new Date(activity.performed_at) : null;
                  const dateStr = dt ? dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '';
                  const timeStr = dt ? dt.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true }) : '';

                  return (
                    <div key={activity.id} className="flex gap-3 group">
                      {/* Icon */}
                      <div className={`mt-1 shrink-0 h-7 w-7 rounded-full flex items-center justify-center ${isNote ? 'bg-primary/10' : 'bg-muted'}`}>
                        <Icon className={`h-3.5 w-3.5 ${isNote ? 'text-primary' : 'text-muted-foreground'}`} />
                      </div>
                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-baseline gap-2 flex-wrap">
                          {!isNote && (
                            <span className="text-xs font-semibold capitalize text-muted-foreground">{activity.activity_type}</span>
                          )}
                          <span className="text-xs text-muted-foreground">{dateStr}</span>
                          <span className="text-xs text-muted-foreground/60">{timeStr}</span>
                        </div>
                        {activity.subject && (
                          <p className="text-sm font-medium mt-0.5">{activity.subject}</p>
                        )}
                        {activity.body && (
                          <p className="text-sm mt-0.5 whitespace-pre-wrap leading-relaxed">{activity.body}</p>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Background Notes — Item 1 & 8 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Background Notes</span>
            {!editingNotes && (
              <Button variant="ghost" size="sm" onClick={startEditingNotes}>
                <Pencil className="h-3.5 w-3.5 mr-1" /> Edit
              </Button>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {editingNotes ? (
            <div className="space-y-2">
              <textarea
                ref={notesRef}
                value={notesDraft}
                onChange={(e) => setNotesDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) saveNotes();
                  if (e.key === 'Escape') setEditingNotes(false);
                }}
                rows={4}
                className="w-full px-3 py-2 text-sm border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-primary resize-none"
                placeholder="Background context, how you met, relevant details..."
              />
              <div className="flex gap-2">
                <Button size="sm" onClick={saveNotes} disabled={notesMutation.isPending}>
                  {notesMutation.isPending ? 'Saving...' : 'Save'}
                </Button>
                <Button size="sm" variant="outline" onClick={() => setEditingNotes(false)}>Cancel</Button>
                <span className="text-xs text-muted-foreground self-center ml-auto">⌘+Enter to save</span>
              </div>
            </div>
          ) : (
            <div
              className="cursor-pointer group min-h-[40px]"
              onClick={startEditingNotes}
            >
              {contact.notes ? (
                <p className="text-sm whitespace-pre-wrap leading-relaxed">{contact.notes}</p>
              ) : (
                <p className="text-sm text-muted-foreground italic">No background notes yet. Click to add.</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span>{value || '—'}</span>
    </div>
  );
}
