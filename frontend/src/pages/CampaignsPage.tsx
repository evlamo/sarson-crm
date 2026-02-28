import { useState, useEffect, useRef, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
import { formatDate } from '@/lib/formatDate';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { Switch } from '@/components/ui/switch';

// ── Helpers ───────────────────────────────────────────────────────────────

function stripHtmlToText(html: string): string {
  if (!html) return '';
  return html
    .replace(/<style[^>]*>.*?<\/style>/gis, '')
    .replace(/<script[^>]*>.*?<\/script>/gis, '')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<p[^>]*>/gi, '\n\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&nbsp;/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

// ── Types ─────────────────────────────────────────────────────────────────

interface Campaign {
  id: string;
  name: string;
  subject: string;
  preview_text: string | null;
  status: string;
  recipient_count: number;
  sent_count: number;
  delivered_count: number;
  open_count: number;
  unique_opens: number;
  click_count: number;
  unique_clicks: number;
  bounce_count: number;
  unsubscribe_count: number;
  spam_count: number;
  from_email: string;
  from_name: string;
  reply_to: string | null;
  body_html: string;
  body_text: string | null;
  segment_id: string | null;
  template_id: string | null;
  mailchimp_campaign_id: string | null;
  mailchimp_audience_id: string | null;
  mailchimp_status: string | null;
  scheduled_at: string | null;
  sent_at: string | null;
  created_at: string;
  updated_at: string;
}

interface Segment {
  id: string;
  name: string;
  contact_count: number;
}

interface Template {
  id: string;
  name: string;
  subject: string | null;
  body_html: string;
  category: string | null;
}

interface Tag {
  id: string;
  name: string;
  contact_count?: number;
}

interface ChecklistItem {
  type: string;
  id: string;
  heading: string;
  details: string;
}

interface SendChecklist {
  is_ready: boolean;
  items: ChecklistItem[];
}

interface MailchimpTemplate {
  id: number;
  name: string;
  thumbnail: string;
}

interface MailchimpStats {
  emails_sent: number;
  unique_opens: number;
  open_rate: number;
  total_opens: number;
  unique_clicks: number;
  click_rate: number;
  total_clicks: number;
  hard_bounces: number;
  soft_bounces: number;
  unsubscribes: number;
  complaints: number;
  last_send_time: string | null;
  error?: string;
}

// ── Constants ─────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700',
  scheduled: 'bg-blue-100 text-blue-700',
  sending: 'bg-yellow-100 text-yellow-700',
  sent: 'bg-green-100 text-green-700',
  cancelled: 'bg-red-100 text-red-700',
  failed: 'bg-red-100 text-red-700',
};

const MERGE_TAGS = [
  { label: 'First Name', tag: '*|FNAME|*' },
  { label: 'Last Name', tag: '*|LNAME|*' },
  { label: 'Email', tag: '*|EMAIL|*' },
  { label: 'Company', tag: '*|COMPANY|*' },
];

const STEP_LABELS = ['Setup', 'Recipients', 'Content', 'Tracking', 'Review & Send'];

// ── Merge Tag Toolbar ─────────────────────────────────────────────────────

function MergeTagToolbar({ onInsert }: { onInsert: (tag: string) => void }) {
  return (
    <div className="flex gap-1.5 flex-wrap mb-2">
      <span className="text-xs text-muted-foreground self-center">Insert:</span>
      {MERGE_TAGS.map(mt => (
        <button
          key={mt.tag}
          type="button"
          onClick={() => onInsert(mt.tag)}
          className="text-xs px-2 py-0.5 rounded border border-dashed border-[#253a52]/40 text-[#253a52] hover:bg-[#253a52]/5 transition-colors"
        >
          {mt.label}
        </button>
      ))}
    </div>
  );
}

// ── Send Checklist Display ────────────────────────────────────────────────

function SendChecklistDisplay({ checklist }: { checklist: SendChecklist }) {
  return (
    <div className="space-y-2">
      {checklist.items.map((item, i) => (
        <div key={i} className={`flex items-start gap-2 p-2.5 rounded-lg ${
          item.type === 'success' ? 'bg-green-50 text-green-700' :
          item.type === 'warning' ? 'bg-yellow-50 text-yellow-700' :
          'bg-red-50 text-red-700'
        }`}>
          <span className="text-sm font-medium shrink-0">
            {item.type === 'success' ? '✓' : item.type === 'warning' ? '⚠' : '✗'}
          </span>
          <div>
            <p className="text-sm font-medium">{item.heading}</p>
            {item.details && <p className="text-xs opacity-80 mt-0.5">{item.details}</p>}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Stats View ────────────────────────────────────────────────────────────

function CampaignStatsView({
  campaign,
  onBack,
}: {
  campaign: Campaign;
  onBack: () => void;
}) {
  const [lastStatsRefresh, setLastStatsRefresh] = useState<string | null>(null);
  const { data: stats, refetch, isLoading } = useQuery<MailchimpStats>({
    queryKey: ['mailchimp-stats', campaign.id],
    queryFn: async () => {
      const res = await api.get(`/campaigns/${campaign.id}/mailchimp-stats`);
      setLastStatsRefresh(new Date().toISOString());
      return res.data;
    },
    enabled: !!campaign.mailchimp_campaign_id,
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <button onClick={onBack} className="text-sm text-[#253a52] hover:underline mb-1">← Back to Campaigns</button>
          <h2 className="text-xl font-bold">{campaign.name}</h2>
          <p className="text-sm text-muted-foreground">{campaign.subject}</p>
        </div>
        <Badge className={STATUS_COLORS[campaign.mailchimp_status || campaign.status] || ''}>
          {campaign.mailchimp_status || campaign.status}
        </Badge>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card>
          <CardContent className="pt-4 pb-3 text-center">
            <p className="text-2xl font-bold">{campaign.recipient_count || stats?.emails_sent || 0}</p>
            <p className="text-xs text-muted-foreground">Sent</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3 text-center">
            <p className="text-2xl font-bold text-blue-600">{stats?.unique_opens ?? campaign.unique_opens ?? 0}</p>
            <p className="text-xs text-muted-foreground">
              Opens {stats?.open_rate ? `(${(stats.open_rate * 100).toFixed(1)}%)` : ''}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3 text-center">
            <p className="text-2xl font-bold text-green-600">{stats?.unique_clicks ?? campaign.unique_clicks ?? 0}</p>
            <p className="text-xs text-muted-foreground">
              Clicks {stats?.click_rate ? `(${(stats.click_rate * 100).toFixed(1)}%)` : ''}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3 text-center">
            <p className="text-2xl font-bold text-red-600">
              {(stats?.hard_bounces ?? 0) + (stats?.soft_bounces ?? 0) || campaign.bounce_count || 0}
            </p>
            <p className="text-xs text-muted-foreground">Bounces</p>
          </CardContent>
        </Card>
      </div>

      {stats && !stats.error && (
        <Card>
          <CardContent className="pt-4 space-y-2 text-sm">
            <div className="flex justify-between"><span>Total Opens</span><span className="font-medium">{stats.total_opens}</span></div>
            <div className="flex justify-between"><span>Total Clicks</span><span className="font-medium">{stats.total_clicks}</span></div>
            <div className="flex justify-between"><span>Hard Bounces</span><span className="font-medium">{stats.hard_bounces}</span></div>
            <div className="flex justify-between"><span>Soft Bounces</span><span className="font-medium">{stats.soft_bounces}</span></div>
            <div className="flex justify-between"><span>Unsubscribes</span><span className="font-medium">{stats.unsubscribes}</span></div>
            <div className="flex justify-between"><span>Spam Complaints</span><span className="font-medium">{stats.complaints}</span></div>
            {stats.last_send_time && (
              <div className="flex justify-between"><span>Sent</span><span className="font-medium">{formatDate(stats.last_send_time)}</span></div>
            )}
          </CardContent>
        </Card>
      )}

      {stats?.error && (
        <p className="text-sm text-muted-foreground italic">{stats.error}</p>
      )}

      {campaign.mailchimp_campaign_id && (
        <div>
          <Button variant="outline" onClick={() => refetch()} disabled={isLoading}>
            {isLoading ? 'Refreshing...' : 'Refresh Stats from Mailchimp'}
          </Button>
          <p className="text-xs text-muted-foreground mt-2">
            📊 Mailchimp stats typically update every 15–30 minutes after send.
            Last refreshed: {lastStatsRefresh ? formatDate(lastStatsRefresh) : 'Never'}
          </p>
        </div>
      )}

      <Card>
        <CardHeader><CardTitle className="text-sm">Details</CardTitle></CardHeader>
        <CardContent className="text-sm space-y-1">
          <p><strong>From:</strong> {campaign.from_name} &lt;{campaign.from_email}&gt;</p>
          {campaign.reply_to && <p><strong>Reply-To:</strong> {campaign.reply_to}</p>}
          {campaign.sent_at && <p><strong>Sent:</strong> {formatDate(campaign.sent_at)}</p>}
          {campaign.scheduled_at && <p><strong>Scheduled:</strong> {formatDate(campaign.scheduled_at)}</p>}
          <p><strong>Created:</strong> {formatDate(campaign.created_at)}</p>
        </CardContent>
      </Card>
    </div>
  );
}

// ── Campaign Builder Wizard ───────────────────────────────────────────────

function CampaignBuilder({
  editCampaign,
  onClose,
}: {
  editCampaign: Campaign | null;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [step, setStep] = useState(1);
  const [campaignId, setCampaignId] = useState<string | null>(editCampaign?.id || null);
  const htmlEditorRef = useRef<HTMLTextAreaElement>(null);

  const [form, setForm] = useState({
    name: editCampaign?.name || '',
    subject: editCampaign?.subject || '',
    preview_text: editCampaign?.preview_text || '',
    from_name: editCampaign?.from_name || 'Sarson Funds',
    from_email: editCampaign?.from_email || '',
    reply_to: editCampaign?.reply_to || '',
    segment_id: editCampaign?.segment_id || '',
    tag_ids: [] as string[],
    body_html: editCampaign?.body_html || '',
    body_text: editCampaign?.body_text || '',
    template_id: editCampaign?.template_id || '',
    tracking_opens: true,
    tracking_html_clicks: true,
    google_analytics_tag: '',
    timewarp: false,
  });

  const [contentTab, setContentTab] = useState<'html' | 'preview' | 'plaintext'>('html');
  const [syncing, setSyncing] = useState(false);
  const [checklist, setChecklist] = useState<SendChecklist | null>(null);
  const [showSendConfirm, setShowSendConfirm] = useState(false);
  const [showSchedule, setShowSchedule] = useState(false);
  const [scheduleTime, setScheduleTime] = useState('');
  const [testEmail, setTestEmail] = useState('');

  const { data: segments = [] } = useQuery<Segment[]>({
    queryKey: ['segments'],
    queryFn: async () => {
      const res = await api.get('/segments');
      return res.data.data || [];
    },
  });

  const { data: tags = [] } = useQuery<Tag[]>({
    queryKey: ['tags'],
    queryFn: async () => {
      const res = await api.get('/tags');
      return res.data.data || res.data || [];
    },
  });

  const { data: templates = [] } = useQuery<Template[]>({
    queryKey: ['templates'],
    queryFn: async () => {
      const res = await api.get('/templates');
      return res.data.data || [];
    },
  });

  const { data: mcTemplates = [] } = useQuery<MailchimpTemplate[]>({
    queryKey: ['mc-templates'],
    queryFn: async () => {
      const res = await api.get('/campaigns/mailchimp/templates');
      return res.data || [];
    },
  });

  const selectedSegment = segments.find((s) => s.id === form.segment_id);

  // Save draft (create or update)
  const saveDraft = useMutation({
    mutationFn: async () => {
      const payload = {
        name: form.name,
        subject: form.subject,
        preview_text: form.preview_text || undefined,
        from_name: form.from_name,
        from_email: form.from_email,
        reply_to: form.reply_to || undefined,
        segment_id: form.segment_id || undefined,
        template_id: form.template_id || undefined,
        body_html: form.body_html || '<p></p>',
        body_text: form.body_text || undefined,
      };
      if (campaignId) {
        const res = await api.patch(`/campaigns/${campaignId}`, payload);
        return res.data;
      } else {
        const res = await api.post('/campaigns', payload);
        return res.data;
      }
    },
    onSuccess: (data) => {
      setCampaignId(data.id);
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
    },
    onError: () => {
      toast.error('Failed to save draft');
    },
  });

  // Auto-save when moving to step 2 (creates the draft)
  const goToStep = async (targetStep: number) => {
    if (targetStep > 1 && !campaignId && form.name && form.subject && form.from_email) {
      await saveDraft.mutateAsync();
    } else if (targetStep > step && campaignId) {
      // Save current state
      saveDraft.mutate();
    }
    setStep(targetStep);
  };

  // Sync to Mailchimp
  const syncToMailchimp = async () => {
    if (!campaignId) {
      toast.error('Save the campaign first');
      return;
    }
    setSyncing(true);
    setChecklist(null);
    try {
      // First ensure latest content is saved
      await saveDraft.mutateAsync();

      // Sync to Mailchimp
      const syncPayload: Record<string, unknown> = {
        tracking_opens: form.tracking_opens,
        tracking_html_clicks: form.tracking_html_clicks,
        google_analytics_tag: form.google_analytics_tag,
      };
      if (form.segment_id) syncPayload.segment_id = form.segment_id;
      if (form.tag_ids.length) syncPayload.tag_ids = form.tag_ids;

      const syncRes = await api.post(`/campaigns/${campaignId}/sync-mailchimp`, syncPayload);
      toast.success(`Synced ${syncRes.data.synced_count} contacts to Mailchimp`);

      // Get send checklist
      const checkRes = await api.get(`/campaigns/${campaignId}/mailchimp-checklist`);
      setChecklist(checkRes.data);

      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Sync failed';
      toast.error(msg);
    } finally {
      setSyncing(false);
    }
  };

  // Send now
  const sendNow = useMutation({
    mutationFn: async () => {
      await api.post(`/campaigns/${campaignId}/send-mailchimp`);
    },
    onSuccess: () => {
      toast.success('Campaign sent!');
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
      onClose();
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Send failed';
      toast.error(msg);
    },
  });

  // Schedule
  const scheduleCampaign = useMutation({
    mutationFn: async () => {
      await api.post(`/campaigns/${campaignId}/schedule-mailchimp`, {
        schedule_time: new Date(scheduleTime).toISOString(),
      });
    },
    onSuccess: () => {
      toast.success('Campaign scheduled!');
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
      onClose();
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Schedule failed';
      toast.error(msg);
    },
  });

  // Send test
  const sendTest = useMutation({
    mutationFn: async () => {
      await api.post(`/campaigns/${campaignId}/send-test`, {
        test_emails: [testEmail],
        send_type: 'html',
      });
    },
    onSuccess: () => {
      toast.success(`Test email sent to ${testEmail}`);
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Test send failed';
      toast.error(msg);
    },
  });

  const insertMergeTag = useCallback((tag: string) => {
    const el = htmlEditorRef.current;
    if (!el) {
      setForm(f => ({ ...f, body_html: f.body_html + tag }));
      return;
    }
    const start = el.selectionStart;
    const end = el.selectionEnd;
    const before = form.body_html.substring(0, start);
    const after = form.body_html.substring(end);
    setForm(f => ({ ...f, body_html: before + tag + after }));
    setTimeout(() => {
      el.selectionStart = el.selectionEnd = start + tag.length;
      el.focus();
    }, 0);
  }, [form.body_html]);

  const applyTemplate = (templateId: string) => {
    const tmpl = templates.find((t) => t.id === templateId);
    if (tmpl) {
      setForm(f => ({
        ...f,
        template_id: templateId,
        body_html: tmpl.body_html || f.body_html,
        subject: tmpl.subject || f.subject,
      }));
    }
  };

  const canProceedStep1 = form.name && form.subject && form.from_email;
  const canProceedStep2 = form.segment_id || form.tag_ids.length > 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <button onClick={onClose} className="text-sm text-[#253a52] hover:underline mb-1">← Back to Campaigns</button>
          <h2 className="text-xl font-bold">{editCampaign ? 'Edit Campaign' : 'New Campaign'}</h2>
        </div>
        <Button variant="outline" size="sm" onClick={() => { saveDraft.mutate(); toast.success('Draft saved'); }}>
          Save Draft
        </Button>
      </div>

      {/* Step indicator */}
      <div className="flex gap-1">
        {STEP_LABELS.map((label, i) => (
          <button
            key={i}
            onClick={() => goToStep(i + 1)}
            className={`flex-1 text-center py-2 text-xs font-medium rounded transition-colors ${
              i + 1 === step
                ? 'bg-[#253a52] text-white'
                : i + 1 < step
                ? 'bg-[#253a52]/20 text-[#253a52] hover:bg-[#253a52]/30'
                : 'bg-muted text-muted-foreground'
            }`}
          >
            {i + 1}. {label}
          </button>
        ))}
      </div>

      {/* ── Step 1: Setup ──────────────────────────────────────────── */}
      {step === 1 && (
        <Card>
          <CardContent className="pt-6 space-y-4">
            <div>
              <Label>Campaign Name <span className="text-red-500">*</span></Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Q1 2026 Newsletter" />
              <p className="text-xs text-muted-foreground mt-1">Internal name — recipients won't see this</p>
            </div>
            <div>
              <Label>Subject Line <span className="text-red-500">*</span></Label>
              <Input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} placeholder="Your Monthly Market Update" />
              <div className="flex justify-between items-center mt-1">
                <span className={`text-xs ${
                  form.subject.length === 0 ? 'text-muted-foreground' :
                  form.subject.length <= 50 ? 'text-green-600' :
                  form.subject.length <= 70 ? 'text-yellow-600' :
                  'text-red-500'
                }`}>
                  {form.subject.length === 0 ? 'Aim for 50–70 characters' :
                   form.subject.length <= 50 ? '✓ Great length' :
                   form.subject.length <= 70 ? '⚠ Getting long — may clip on mobile' :
                   '✗ Too long — will be clipped in most inboxes'}
                </span>
                <span className={`text-xs font-mono ${form.subject.length > 70 ? 'text-red-500' : form.subject.length > 50 ? 'text-yellow-600' : 'text-muted-foreground'}`}>
                  {form.subject.length}/70
                </span>
              </div>
            </div>
            <div>
              <Label>Preview Text</Label>
              <Input value={form.preview_text} onChange={(e) => setForm({ ...form, preview_text: e.target.value })} placeholder="Shows after subject in inbox..." />
              <p className={`text-xs mt-1 ${form.preview_text.length > 100 ? 'text-yellow-600' : 'text-muted-foreground'}`}>
                {form.preview_text.length}/100 characters — the snippet shown after subject in the inbox
              </p>
            </div>
            <Separator />
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <Label>From Name</Label>
                <Input value={form.from_name} onChange={(e) => setForm({ ...form, from_name: e.target.value })} />
              </div>
              <div>
                <Label>From Email <span className="text-red-500">*</span></Label>
                <Input value={form.from_email} onChange={(e) => setForm({ ...form, from_email: e.target.value })} placeholder="info@sarsonfunds.com" />
              </div>
              <div>
                <Label>Reply-To Email</Label>
                <Input value={form.reply_to} onChange={(e) => setForm({ ...form, reply_to: e.target.value })} placeholder="Same as From if blank" />
              </div>
            </div>
            <div className="flex justify-end">
              <Button onClick={() => goToStep(2)} disabled={!canProceedStep1}>Next: Recipients →</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Step 2: Recipients ─────────────────────────────────────── */}
      {step === 2 && (
        <Card>
          <CardContent className="pt-6 space-y-4">
            <div>
              <Label>Segment</Label>
              <Select value={form.segment_id} onValueChange={(v) => setForm({ ...form, segment_id: v })}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a segment..." />
                </SelectTrigger>
                <SelectContent>
                  {segments.map((seg) => (
                    <SelectItem key={seg.id} value={seg.id}>
                      {seg.name} {seg.contact_count != null ? `(${seg.contact_count.toLocaleString()})` : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {tags.length > 0 && (
              <div>
                <Label>Or select specific tags</Label>
                <div className="flex flex-wrap gap-2 mt-1">
                  {tags.map((tag) => (
                    <button
                      key={tag.id}
                      type="button"
                      onClick={() => {
                        setForm(f => ({
                          ...f,
                          tag_ids: f.tag_ids.includes(tag.id)
                            ? f.tag_ids.filter(t => t !== tag.id)
                            : [...f.tag_ids, tag.id],
                        }));
                      }}
                      className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                        form.tag_ids.includes(tag.id)
                          ? 'bg-[#253a52] text-white border-[#253a52]'
                          : 'border-gray-300 hover:border-[#253a52]/50'
                      }`}
                    >
                      {tag.name} {tag.contact_count != null ? `(${tag.contact_count})` : ''}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {selectedSegment && (
              <div className="bg-blue-50 text-blue-700 p-3 rounded-lg text-sm">
                This campaign will reach ~<strong>{selectedSegment.contact_count?.toLocaleString() || '?'}</strong> contacts
              </div>
            )}
            {!form.segment_id && form.tag_ids.length === 0 && (
              <div className="bg-yellow-50 text-yellow-700 p-3 rounded-lg text-sm">
                Select a segment or tags to define your audience
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              Contacts will be synced to your Mailchimp audience before sending
            </p>

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(1)}>← Setup</Button>
              <Button onClick={() => goToStep(3)} disabled={!canProceedStep2}>Next: Content →</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Step 3: Content Editor ─────────────────────────────────── */}
      {step === 3 && (
        <Card>
          <CardContent className="pt-6 space-y-4">
            {templates.length > 0 && (
              <div>
                <Label>Start from template</Label>
                <Select value={form.template_id} onValueChange={applyTemplate}>
                  <SelectTrigger>
                    <SelectValue placeholder="Choose a template..." />
                  </SelectTrigger>
                  <SelectContent>
                    {templates.map((t) => (
                      <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* Mailchimp Templates */}
            {mcTemplates.length > 0 && (
              <div>
                <Label>Start from Mailchimp Template</Label>
                <Select onValueChange={async (v) => {
                  try {
                    const res = await api.get(`/campaigns/mailchimp/templates/${v}/content`);
                    if (res.data.html) {
                      setForm(f => ({ ...f, body_html: res.data.html }));
                      toast.success('Template loaded');
                    }
                  } catch { toast.error('Failed to load template'); }
                }}>
                  <SelectTrigger>
                    <SelectValue placeholder="Choose a Mailchimp template..." />
                  </SelectTrigger>
                  <SelectContent>
                    {mcTemplates.map((t) => (
                      <SelectItem key={t.id} value={String(t.id)}>{t.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* Tab bar */}
            <div className="flex border-b">
              {(['html', 'preview', 'plaintext'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setContentTab(tab)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                    contentTab === tab
                      ? 'border-[#253a52] text-[#253a52]'
                      : 'border-transparent text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {tab === 'html' ? 'HTML Editor' : tab === 'preview' ? 'Preview' : 'Plain Text'}
                </button>
              ))}
            </div>

            {contentTab === 'html' && (
              <div>
                <MergeTagToolbar onInsert={insertMergeTag} />
                <textarea
                  ref={htmlEditorRef}
                  className="w-full border rounded-md p-3 text-sm min-h-[350px] font-mono focus:outline-none focus:ring-2 focus:ring-[#253a52]/30"
                  value={form.body_html}
                  onChange={(e) => setForm({ ...form, body_html: e.target.value })}
                  placeholder="<p>Hi *|FNAME|*,</p>&#10;&#10;<p>Your content here...</p>"
                />
              </div>
            )}

            {contentTab === 'preview' && (
              <div>
                {/* Inbox preview bar */}
                <div className="bg-gray-50 border rounded-t-lg p-3 font-mono text-xs text-gray-600 border-b">
                  <div><span className="font-bold text-gray-800">From:</span> {form.from_name || 'Sarson Funds'} &lt;{form.from_email || 'info@sarsonfunds.com'}&gt;</div>
                  <div><span className="font-bold text-gray-800">Subject:</span> {form.subject || '(No subject)'}</div>
                  <div><span className="font-bold text-gray-800">Preview:</span> <span className="text-gray-400">{form.preview_text || '(No preview text set)'}</span></div>
                </div>
                {/* 600px standard email width */}
                <div className="bg-gray-100 p-4 rounded-b-lg flex justify-center overflow-auto">
                  <div className="w-[600px] min-w-[600px] bg-white shadow-lg">
                    <iframe
                      title="Email Preview"
                      srcDoc={form.body_html || '<p style="color:#999;padding:20px;">No content yet</p>'}
                      className="w-full border-0"
                      style={{ height: '500px', minHeight: '500px' }}
                      sandbox="allow-same-origin"
                    />
                  </div>
                </div>
              </div>
            )}

            {contentTab === 'plaintext' && (
              <div className="border rounded-lg bg-gray-50 p-4 font-mono text-sm text-gray-700 whitespace-pre-wrap min-h-[300px] max-h-[500px] overflow-y-auto">
                {stripHtmlToText(form.body_html) || (
                  <span className="text-gray-400 italic">Write your HTML content to see plain text preview</span>
                )}
                <p className="text-xs text-muted-foreground mt-4 italic font-sans not-italic border-t pt-2">
                  Plain text is auto-generated when sending. Mailchimp uses this as fallback for email clients that don't support HTML.
                </p>
              </div>
            )}

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(2)}>← Recipients</Button>
              <Button onClick={() => goToStep(4)} disabled={!form.body_html}>Next: Tracking →</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Step 4: Tracking & Settings ────────────────────────────── */}
      {step === 4 && (
        <Card>
          <CardContent className="pt-6 space-y-4">
            <div className="space-y-3">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.tracking_opens}
                  onChange={(e) => setForm({ ...form, tracking_opens: e.target.checked })}
                  className="w-4 h-4 rounded border-gray-300"
                />
                <div>
                  <p className="text-sm font-medium">Track Opens</p>
                  <p className="text-xs text-muted-foreground">Monitor how many recipients open your email</p>
                </div>
              </label>
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.tracking_html_clicks}
                  onChange={(e) => setForm({ ...form, tracking_html_clicks: e.target.checked })}
                  className="w-4 h-4 rounded border-gray-300"
                />
                <div>
                  <p className="text-sm font-medium">Track Clicks</p>
                  <p className="text-xs text-muted-foreground">Monitor link clicks in your email</p>
                </div>
              </label>
            </div>
            <Separator />
            <div className="flex items-center justify-between p-3 border rounded-lg">
              <div>
                <p className="text-sm font-medium">Send Time Optimization</p>
                <p className="text-xs text-muted-foreground">Let Mailchimp choose the best send time for each recipient based on their past engagement</p>
              </div>
              <Switch checked={form.timewarp || false} onCheckedChange={(v) => setForm(f => ({...f, timewarp: v}))} />
            </div>
            {form.timewarp && (
              <div className="flex items-center gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700">
                <span>ℹ️</span>
                <span>Send Time Optimization requires scheduling — use "Schedule Send" instead of "Send Now".</span>
              </div>
            )}
            <Separator />
            <div>
              <Label>Google Analytics Campaign Tag</Label>
              <Input
                value={form.google_analytics_tag}
                onChange={(e) => setForm({ ...form, google_analytics_tag: e.target.value })}
                placeholder="e.g. sarson-newsletter-march-2026"
              />
              <p className="text-xs text-muted-foreground mt-1">Optional — adds UTM tracking to all links</p>
            </div>
            <div className="bg-blue-50 text-blue-700 p-3 rounded-lg text-sm">
              <strong>CAN-SPAM Compliance:</strong> Mailchimp automatically adds an unsubscribe footer to all campaigns (auto_footer enabled).
            </div>
            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(3)}>← Content</Button>
              <Button onClick={() => goToStep(5)}>Next: Review & Send →</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Step 5: Review & Send ──────────────────────────────────── */}
      {step === 5 && (
        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Campaign Summary</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="grid grid-cols-2 gap-y-2">
                <span className="text-muted-foreground">Name</span>
                <span className="font-medium">{form.name}</span>
                <span className="text-muted-foreground">Subject</span>
                <span className="font-medium">{form.subject}</span>
                {form.preview_text && (
                  <>
                    <span className="text-muted-foreground">Preview Text</span>
                    <span>{form.preview_text}</span>
                  </>
                )}
                <span className="text-muted-foreground">From</span>
                <span>{form.from_name} &lt;{form.from_email}&gt;</span>
                <span className="text-muted-foreground">Audience</span>
                <span>{selectedSegment?.name || 'Tags selected'} ({selectedSegment?.contact_count?.toLocaleString() || '?'} contacts)</span>
                <span className="text-muted-foreground">Tracking</span>
                <span>
                  {[form.tracking_opens && 'Opens', form.tracking_html_clicks && 'Clicks'].filter(Boolean).join(', ') || 'None'}
                  {form.google_analytics_tag && ` • GA: ${form.google_analytics_tag}`}
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Sync Button */}
          <Button
            onClick={syncToMailchimp}
            disabled={syncing}
            className="w-full bg-[#253a52] hover:bg-[#253a52]/90"
          >
            {syncing ? (
              <span className="flex items-center gap-2">
                <span className="animate-spin">⟳</span> Syncing to Mailchimp...
              </span>
            ) : checklist ? (
              'Re-sync to Mailchimp'
            ) : (
              'Sync to Mailchimp'
            )}
          </Button>

          {/* Checklist */}
          {checklist && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <h3 className="font-medium text-sm">Send Checklist</h3>
                <Badge className={checklist.is_ready ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}>
                  {checklist.is_ready ? 'Ready to Send' : 'Not Ready'}
                </Badge>
              </div>
              <SendChecklistDisplay checklist={checklist} />
            </div>
          )}

          {/* Test Send */}
          {checklist && campaignId && (
            <Card>
              <CardContent className="pt-4">
                <Label className="text-sm">Send Test Email</Label>
                <div className="flex gap-2 mt-1">
                  <Input
                    value={testEmail}
                    onChange={(e) => setTestEmail(e.target.value)}
                    placeholder="your@email.com"
                    type="email"
                    className="flex-1"
                  />
                  <Button
                    variant="outline"
                    onClick={() => sendTest.mutate()}
                    disabled={!testEmail || sendTest.isPending}
                  >
                    {sendTest.isPending ? 'Sending...' : 'Send Test'}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Send / Schedule buttons */}
          {checklist?.is_ready && (
            <div className="flex gap-3">
              <Button
                className="flex-1 bg-green-600 hover:bg-green-700 text-white"
                onClick={() => {
                  if (form.timewarp) {
                    toast.error('Send Time Optimization requires scheduling. Use "Schedule Send" instead.');
                    return;
                  }
                  setShowSendConfirm(true);
                }}
              >
                Send Now
              </Button>
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => setShowSchedule(true)}
              >
                Schedule
              </Button>
            </div>
          )}

          <div className="flex justify-between">
            <Button variant="outline" onClick={() => setStep(4)}>← Tracking</Button>
          </div>
        </div>
      )}

      {/* Send Confirmation Dialog */}
      <Dialog open={showSendConfirm} onOpenChange={setShowSendConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Send</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            You're about to send "<strong>{form.name}</strong>" to{' '}
            <strong>{selectedSegment?.contact_count?.toLocaleString() || '?'}</strong> contacts.
            This action cannot be undone.
          </p>
          <div className="flex justify-end gap-2 mt-4">
            <Button variant="outline" onClick={() => setShowSendConfirm(false)}>Cancel</Button>
            <Button
              className="bg-green-600 hover:bg-green-700 text-white"
              onClick={() => { sendNow.mutate(); setShowSendConfirm(false); }}
              disabled={sendNow.isPending}
            >
              {sendNow.isPending ? 'Sending...' : 'Yes, Send Now'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Schedule Dialog */}
      <Dialog open={showSchedule} onOpenChange={setShowSchedule}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Schedule Campaign</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Send Date & Time</Label>
              <Input
                type="datetime-local"
                value={scheduleTime}
                onChange={(e) => setScheduleTime(e.target.value)}
              />
              <p className="text-xs text-muted-foreground mt-1">Time will be sent in UTC to Mailchimp</p>
            </div>
          </div>
          <div className="flex justify-end gap-2 mt-4">
            <Button variant="outline" onClick={() => setShowSchedule(false)}>Cancel</Button>
            <Button
              onClick={() => { scheduleCampaign.mutate(); setShowSchedule(false); }}
              disabled={!scheduleTime || scheduleCampaign.isPending}
            >
              {scheduleCampaign.isPending ? 'Scheduling...' : 'Schedule'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ── Main Campaigns Page ───────────────────────────────────────────────────

type ViewMode = { type: 'list' } | { type: 'builder'; campaign: Campaign | null } | { type: 'stats'; campaign: Campaign };

export default function CampaignsPage() {
  const isAdmin = useAuth((s) => s.isAdmin);
  const [view, setView] = useState<ViewMode>({ type: 'list' });

  useEffect(() => { document.title = 'Campaigns — Sarson Funds CRM'; }, []);

  const queryClient = useQueryClient();

  const { data: campaigns = [], isLoading } = useQuery<Campaign[]>({
    queryKey: ['campaigns'],
    queryFn: async () => {
      const res = await api.get('/campaigns');
      return res.data.data || [];
    },
  });

  const deleteCampaign = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/campaigns/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
      toast.success('Campaign deleted');
    },
    onError: () => toast.error('Failed to delete campaign'),
  });

  const duplicateCampaign = useMutation({
    mutationFn: async (id: string) => {
      await api.post(`/campaigns/${id}/duplicate`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
      toast.success('Campaign duplicated');
    },
    onError: () => toast.error('Failed to duplicate'),
  });

  if (view.type === 'builder') {
    return (
      <CampaignBuilder
        editCampaign={view.campaign}
        onClose={() => setView({ type: 'list' })}
      />
    );
  }

  if (view.type === 'stats') {
    return (
      <CampaignStatsView
        campaign={view.campaign}
        onBack={() => setView({ type: 'list' })}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Campaigns</h1>
        {isAdmin ? (
          <Button onClick={() => setView({ type: 'builder', campaign: null })} className="bg-[#253a52] hover:bg-[#253a52]/90">
            + New Campaign
          </Button>
        ) : (
          <Button disabled title="Admin only">🔒 New Campaign</Button>
        )}
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading campaigns...</p>
      ) : !campaigns.length ? (
        <Card>
          <CardContent className="py-16 text-center">
            <p className="text-lg font-medium text-muted-foreground mb-2">No campaigns yet</p>
            <p className="text-sm text-muted-foreground mb-4">Create your first email campaign to get started</p>
            {isAdmin && (
              <Button onClick={() => setView({ type: 'builder', campaign: null })} className="bg-[#253a52] hover:bg-[#253a52]/90">
                Create Campaign
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {campaigns.map((c) => {
            const isSent = ['sent', 'sending'].includes(c.status) || ['sent', 'sending'].includes(c.mailchimp_status || '');
            const openRate = c.recipient_count > 0 ? ((c.unique_opens / c.recipient_count) * 100).toFixed(1) : '—';
            const clickRate = c.recipient_count > 0 ? ((c.unique_clicks / c.recipient_count) * 100).toFixed(1) : '—';

            return (
              <Card key={c.id} className="hover:shadow-sm transition-shadow">
                <CardContent className="flex items-center justify-between py-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <h3 className="font-medium truncate">{c.name}</h3>
                      <Badge className={STATUS_COLORS[c.mailchimp_status || c.status] || 'bg-gray-100 text-gray-700'}>
                        {c.mailchimp_status || c.status}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground truncate">{c.subject}</p>
                    <div className="flex gap-3 mt-1 text-xs text-muted-foreground">
                      {c.recipient_count > 0 && <span>{c.recipient_count.toLocaleString()} recipients</span>}
                      {isSent && (
                        <>
                          <span>Opens: {openRate}%</span>
                          <span>Clicks: {clickRate}%</span>
                        </>
                      )}
                      <span>{formatDate(c.sent_at || c.updated_at || c.created_at)}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 ml-4 shrink-0">
                    {c.status === 'draft' && isAdmin && (
                      <>
                        <Button size="sm" variant="outline" onClick={() => setView({ type: 'builder', campaign: c })}>
                          Edit
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => duplicateCampaign.mutate(c.id)}>
                          Duplicate
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-red-600 hover:text-red-700"
                          onClick={() => {
                            if (confirm('Delete this campaign?')) deleteCampaign.mutate(c.id);
                          }}
                        >
                          Delete
                        </Button>
                      </>
                    )}
                    {isSent && (
                      <Button size="sm" variant="outline" onClick={() => setView({ type: 'stats', campaign: c })}>
                        View Stats
                      </Button>
                    )}
                    {c.status === 'scheduled' && (
                      <Button size="sm" variant="outline" onClick={() => setView({ type: 'stats', campaign: c })}>
                        Details
                      </Button>
                    )}
                    {!isSent && c.status !== 'draft' && c.status !== 'scheduled' && (
                      <Button size="sm" variant="outline" onClick={() => duplicateCampaign.mutate(c.id)}>
                        Duplicate
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
