import { useState, useEffect, useRef } from 'react';
import { formatDate, formatTime } from '@/lib/formatDate';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useNavigate } from '@tanstack/react-router';
import { toast } from 'sonner';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { ArrowLeft, Mail, Phone, MessageSquare, Calendar, FileText, CheckCircle } from 'lucide-react';
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
  profile_url: string | null;
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

const STATUS_OPTIONS = [
  { value: 'hot', label: 'Hot' },
  { value: 'warm', label: 'Warm' },
  { value: 'prospect', label: 'Prospect' },
  { value: 'cold', label: 'Cold' },
  { value: 'poc', label: 'POC' },
  { value: 'active', label: 'Active' },
  { value: 'na', label: 'N/A' },
];

const LEAD_SOURCE_OPTIONS = [
  { value: 'website', label: 'Website' },
  { value: 'referral', label: 'Referral' },
  { value: 'linkedin', label: 'LinkedIn' },
  { value: 'conference', label: 'Conference' },
  { value: 'cold_outreach', label: 'Cold Outreach' },
  { value: 'inbound', label: 'Inbound' },
  { value: 'import', label: 'Import' },
  { value: 'other', label: 'Other' },
];

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

  const toggleContacted = () => {
    if (contact) {
      updateMutation.mutate({ contacted: !contact.contacted });
    }
  };

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

  const fullName = [contact.first_name, contact.middle_name, contact.last_name].filter(Boolean).join(' ') || 'Unnamed Contact';

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
            {contact.title}{contact.title && (contact.company_name || contact.company) ? ' at ' : ''}{contact.company_name || contact.company}
          </p>
        </div>
        <Button
          variant={contact.contacted ? 'default' : 'outline'}
          size="sm"
          onClick={toggleContacted}
        >
          {contact.contacted ? '✓ Contacted' : 'Mark Contacted'}
        </Button>
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
        {/* Left Column — Editable Fields */}
        <div className="space-y-6 lg:col-span-1">
          {/* Contact Info */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Contact Info</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <FieldRow label="First Name">
                <EditableField value={contact.first_name} onSave={(v) => savePatch('first_name', v)} placeholder="Add first name..." />
              </FieldRow>
              <FieldRow label="Middle Name">
                <EditableField value={contact.middle_name} onSave={(v) => savePatch('middle_name', v)} placeholder="Add middle name..." />
              </FieldRow>
              <FieldRow label="Last Name">
                <EditableField value={contact.last_name} onSave={(v) => savePatch('last_name', v)} placeholder="Add last name..." />
              </FieldRow>
              <FieldRow label="Email">
                <EditableField value={contact.email} type="email" onSave={(v) => savePatch('email', v)} placeholder="Add email..." />
              </FieldRow>
              <FieldRow label="Phone">
                <EditableField value={contact.phone} type="tel" onSave={(v) => savePatch('phone', v)} placeholder="Add phone..." hint="+1234567890" />
              </FieldRow>
              <FieldRow label="Title">
                <EditableField value={contact.title} onSave={(v) => savePatch('title', v)} placeholder="Add title..." />
              </FieldRow>
            </CardContent>
          </Card>

          {/* Company */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Company</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <FieldRow label="Company">
                <CompanyCombobox
                  companyName={contact.company_name || contact.company}
                  companyId={contact.company_id}
                  onSave={async (name, selectedCompanyId) => {
                    const payload: Record<string, unknown> = { company: name };
                    if (selectedCompanyId) {
                      payload.company_id = selectedCompanyId;
                    }
                    await patchContact(payload);
                    queryClient.invalidateQueries({ queryKey: ['contact', contactId] });
                    toast.success('Company updated');
                  }}
                  onNavigate={() => navigate({ to: '/companies' })}
                />
              </FieldRow>
            </CardContent>
          </Card>

          {/* Location */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Location</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <FieldRow label="City">
                <EditableField value={contact.city} onSave={(v) => savePatch('city', v)} placeholder="Add city..." />
              </FieldRow>
              <FieldRow label="State">
                <EditableField value={contact.state} onSave={(v) => savePatch('state', v)} placeholder="Add state..." />
              </FieldRow>
              <FieldRow label="Country">
                <EditableField value={contact.country} onSave={(v) => savePatch('country', v)} placeholder="Add country..." />
              </FieldRow>
            </CardContent>
          </Card>

          {/* Online */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Online</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <FieldRow label="LinkedIn">
                <EditableField
                  value={contact.linkedin_url}
                  type="url"
                  onSave={(v) => savePatch('linkedin_url', v)}
                  placeholder="Add LinkedIn URL..."
                  linkHref={contact.linkedin_url || undefined}
                />
              </FieldRow>
              <FieldRow label="Website">
                <EditableField
                  value={contact.website}
                  type="url"
                  onSave={(v) => savePatch('website', v)}
                  placeholder="Add website..."
                  linkHref={contact.website || undefined}
                />
              </FieldRow>
              <FieldRow label="Profile">
                <EditableField
                  value={contact.profile_url}
                  type="url"
                  onSave={(v) => savePatch('profile_url', v)}
                  placeholder="Add profile URL..."
                  linkHref={contact.profile_url || undefined}
                />
              </FieldRow>
            </CardContent>
          </Card>

          {/* CRM */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">CRM</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <FieldRow label="Status">
                <EditableField
                  value={contact.status}
                  type="select"
                  options={STATUS_OPTIONS}
                  onSave={(v) => savePatch('status', v)}
                />
              </FieldRow>
              <FieldRow label="Lead Source">
                <EditableField
                  value={contact.source || contact.lead_source}
                  type="select"
                  options={LEAD_SOURCE_OPTIONS}
                  onSave={(v) => savePatch('source', v)}
                />
              </FieldRow>
              <div className="flex justify-between items-center min-h-[24px]">
                <span className="text-muted-foreground shrink-0">Sales Rep</span>
                <RepAssignPopover
                  contactId={contact.id}
                  currentRep={contact.sarson_rep}
                  variant="detail"
                />
              </div>
              <FieldRow label="Next Step">
                <EditableField value={contact.next_step} onSave={(v) => savePatch('next_step', v)} placeholder="Add next step..." />
              </FieldRow>
              {contact.last_contacted_at && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Last Contacted</span>
                  <span>{formatDate(contact.last_contacted_at)}</span>
                </div>
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
            </CardContent>
          </Card>
        </div>

        {/* Right Column — Activity + Notes */}
        <div className="lg:col-span-2 space-y-6">
          {/* Activity Timeline */}
          <Card>
            <CardHeader>
              <CardTitle>Notes & Activity</CardTitle>
            </CardHeader>
            <CardContent>
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

              <div className="space-y-3 mt-4">
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

          {/* Background Notes */}
          <Card>
            <CardHeader>
              <CardTitle>Background Notes</CardTitle>
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

function FieldRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between items-center min-h-[24px]">
      <span className="text-muted-foreground shrink-0 mr-3">{label}</span>
      <div className="flex-1 text-right">{children}</div>
    </div>
  );
}
