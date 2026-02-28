import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
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

interface Campaign {
  id: string;
  name: string;
  subject: string;
  status: string;
  recipient_count: number;
  sent_count: number;
  delivered_count: number;
  open_count: number;
  unique_opens: number;
  click_count: number;
  bounce_count: number;
  from_email: string;
  from_name: string;
  body_html: string;
  body_text: string | null;
  segment_id: string | null;
  template_id: string | null;
  created_at: string;
  sent_at: string | null;
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

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-800',
  scheduled: 'bg-blue-100 text-blue-800',
  sending: 'bg-yellow-100 text-yellow-800',
  sent: 'bg-green-100 text-green-800',
  cancelled: 'bg-red-100 text-red-800',
  failed: 'bg-red-100 text-red-800',
};

// ── Campaign Builder Wizard ───────────────────────────────────────────────

function CampaignWizard({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    name: '',
    subject: '',
    from_name: 'Sarson Funds',
    from_email: '',
    reply_to: '',
    segment_id: '',
    template_id: '',
    body_html: '',
    body_text: '',
    preview_text: '',
  });

  const { data: segments = [] } = useQuery<Segment[]>({
    queryKey: ['segments'],
    queryFn: async () => {
      const res = await api.get('/segments');
      return res.data.data || [];
    },
    enabled: open,
  });

  const { data: templates = [] } = useQuery<Template[]>({
    queryKey: ['templates'],
    queryFn: async () => {
      const res = await api.get('/templates');
      return res.data.data || [];
    },
    enabled: open,
  });

  const selectedSegment = segments.find((s) => s.id === form.segment_id);
  const selectedTemplate = templates.find((t) => t.id === form.template_id);

  const createAndSend = useMutation({
    mutationFn: async () => {
      // Create campaign
      const res = await api.post('/campaigns', {
        name: form.name,
        subject: form.subject,
        from_name: form.from_name,
        from_email: form.from_email,
        reply_to: form.reply_to || undefined,
        segment_id: form.segment_id || undefined,
        template_id: form.template_id || undefined,
        body_html: form.body_html || selectedTemplate?.body_html || '<p>Empty</p>',
        body_text: form.body_text || undefined,
        preview_text: form.preview_text || undefined,
      });
      // Send it
      await api.post(`/campaigns/${res.data.id}/send`);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
      toast.success('Campaign sent!');
      onClose();
      setStep(1);
    },
    onError: () => {
      toast.error('Failed to send campaign');
    },
  });

  const saveDraft = useMutation({
    mutationFn: async () => {
      await api.post('/campaigns', {
        name: form.name,
        subject: form.subject,
        from_name: form.from_name,
        from_email: form.from_email,
        reply_to: form.reply_to || undefined,
        segment_id: form.segment_id || undefined,
        template_id: form.template_id || undefined,
        body_html: form.body_html || selectedTemplate?.body_html || '<p>Empty</p>',
        body_text: form.body_text || undefined,
        preview_text: form.preview_text || undefined,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
      toast.success('Draft saved');
      onClose();
      setStep(1);
    },
    onError: () => {
      toast.error('Failed to save draft');
    },
  });

  // Apply template to form
  const applyTemplate = (templateId: string) => {
    const tmpl = templates.find((t) => t.id === templateId);
    setForm({
      ...form,
      template_id: templateId,
      body_html: tmpl?.body_html || form.body_html,
      subject: tmpl?.subject || form.subject,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>New Campaign — Step {step} of 4</DialogTitle>
        </DialogHeader>

        {/* Step indicator */}
        <div className="flex gap-2 mb-4">
          {[1, 2, 3, 4].map((s) => (
            <div
              key={s}
              className={`h-1.5 flex-1 rounded ${s <= step ? 'bg-primary' : 'bg-muted'}`}
            />
          ))}
        </div>

        {/* Step 1: Select Segment */}
        {step === 1 && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">Choose your audience</p>
            <div className="space-y-2">
              {segments.map((seg) => (
                <div
                  key={seg.id}
                  className={`p-3 border rounded-md cursor-pointer transition-colors ${
                    form.segment_id === seg.id ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'
                  }`}
                  onClick={() => setForm({ ...form, segment_id: seg.id })}
                >
                  <div className="flex justify-between">
                    <span className="font-medium">{seg.name}</span>
                    {seg.contact_count != null && (
                      <Badge variant="secondary">{seg.contact_count.toLocaleString()} contacts</Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
            <Button onClick={() => setStep(2)} disabled={!form.segment_id}>
              Next →
            </Button>
          </div>
        )}

        {/* Step 2: Select/Create Template */}
        {step === 2 && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">Choose or create email content</p>

            {templates.length > 0 && (
              <div className="space-y-2">
                <Label>Use a Template</Label>
                {templates.map((tmpl) => (
                  <div
                    key={tmpl.id}
                    className={`p-3 border rounded-md cursor-pointer transition-colors ${
                      form.template_id === tmpl.id ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'
                    }`}
                    onClick={() => applyTemplate(tmpl.id)}
                  >
                    <span className="font-medium">{tmpl.name}</span>
                    {tmpl.category && (
                      <Badge variant="outline" className="ml-2 text-xs">{tmpl.category}</Badge>
                    )}
                  </div>
                ))}
                <Separator />
              </div>
            )}

            <div>
              <Label>Subject</Label>
              <Input
                value={form.subject}
                onChange={(e) => setForm({ ...form, subject: e.target.value })}
                placeholder="Email subject line (supports {{first_name}} merge tags)"
              />
            </div>
            <div>
              <Label>Email Body (HTML)</Label>
              <textarea
                className="w-full border rounded-md p-2 text-sm min-h-[200px] font-mono"
                value={form.body_html}
                onChange={(e) => setForm({ ...form, body_html: e.target.value })}
                placeholder="<p>Hi {{first_name}},</p>"
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Available merge tags: {'{{first_name}}'}, {'{{last_name}}'}, {'{{full_name}}'}, {'{{company}}'}, {'{{email}}'}, {'{{unsubscribe_url}}'}
            </p>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setStep(1)}>← Back</Button>
              <Button onClick={() => setStep(3)} disabled={!form.subject || !form.body_html}>
                Next →
              </Button>
            </div>
          </div>
        )}

        {/* Step 3: Preview */}
        {step === 3 && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">Preview your email</p>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Subject: {form.subject}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="border rounded-md p-4 bg-white">
                  <div
                    className="prose prose-sm max-w-none"
                    dangerouslySetInnerHTML={{
                      __html: form.body_html
                        .replace(/\{\{first_name\}\}/g, 'John')
                        .replace(/\{\{last_name\}\}/g, 'Doe')
                        .replace(/\{\{full_name\}\}/g, 'John Doe')
                        .replace(/\{\{company\}\}/g, 'Acme Corp')
                        .replace(/\{\{email\}\}/g, 'john@acme.com')
                        .replace(/\{\{unsubscribe_url\}\}/g, '#'),
                    }}
                  />
                </div>
              </CardContent>
            </Card>

            <div className="text-sm text-muted-foreground">
              Audience: <strong>{selectedSegment?.name}</strong>
              {selectedSegment?.contact_count != null && ` (${selectedSegment.contact_count.toLocaleString()} contacts)`}
            </div>

            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setStep(2)}>← Back</Button>
              <Button onClick={() => setStep(4)}>Next →</Button>
            </div>
          </div>
        )}

        {/* Step 4: Confirm & Send */}
        {step === 4 && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">Confirm campaign details</p>

            <div className="space-y-3">
              <div>
                <Label>Campaign Name</Label>
                <Input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Q1 2026 LP Update"
                />
              </div>
              <div>
                <Label>From Name</Label>
                <Input value={form.from_name} onChange={(e) => setForm({ ...form, from_name: e.target.value })} />
              </div>
              <div>
                <Label>From Email</Label>
                <Input value={form.from_email} onChange={(e) => setForm({ ...form, from_email: e.target.value })} placeholder="team@sarsonfunds.com" />
              </div>
              <div>
                <Label>Reply-To Email</Label>
                <Input value={form.reply_to} onChange={(e) => setForm({ ...form, reply_to: e.target.value })} placeholder="team@sarsonfunds.com" />
              </div>
            </div>

            <Separator />

            <div className="text-sm space-y-1">
              <p><strong>Subject:</strong> {form.subject}</p>
              <p><strong>Audience:</strong> {selectedSegment?.name} ({selectedSegment?.contact_count?.toLocaleString() || '?'} contacts)</p>
              {selectedTemplate && <p><strong>Template:</strong> {selectedTemplate.name}</p>}
            </div>

            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setStep(3)}>← Back</Button>
              <Button
                variant="outline"
                onClick={() => saveDraft.mutate()}
                disabled={saveDraft.isPending || !form.name || !form.from_email}
              >
                Save Draft
              </Button>
              <Button
                onClick={() => createAndSend.mutate()}
                disabled={createAndSend.isPending || !form.name || !form.from_email}
              >
                {createAndSend.isPending ? 'Sending...' : 'Send Now'}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ── Campaigns List ────────────────────────────────────────────────────────

export default function CampaignsPage() {
  const isAdmin = useAuth((s) => s.isAdmin);
  const [wizardOpen, setWizardOpen] = useState(false);

  useEffect(() => { document.title = 'Campaigns — Sarson Funds CRM'; }, []);

  const { data: campaigns = [], isLoading } = useQuery<Campaign[]>({
    queryKey: ['campaigns'],
    queryFn: async () => {
      const res = await api.get('/campaigns');
      return res.data.data || [];
    },
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Campaigns</h1>
        {isAdmin ? (
          <Button onClick={() => setWizardOpen(true)}>+ New Campaign</Button>
        ) : (
          <Button disabled title="Admin only">
            🔒 New Campaign
          </Button>
        )}
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : !campaigns.length ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No campaigns yet. Create your first one!
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {campaigns.map((c) => (
            <Card key={c.id}>
              <CardContent className="flex items-center justify-between py-4">
                <div>
                  <h3 className="font-medium">{c.name}</h3>
                  <p className="text-sm text-muted-foreground">{c.subject}</p>
                </div>
                <div className="flex items-center gap-4">
                  <Badge className={STATUS_COLORS[c.status] || ''}>
                    {c.status}
                  </Badge>
                  {c.status === 'sent' && (
                    <div className="text-xs text-muted-foreground space-x-3">
                      <span>Sent: {c.sent_count}</span>
                      <span>Opens: {c.unique_opens}</span>
                      <span>Clicks: {c.click_count}</span>
                    </div>
                  )}
                  <span className="text-xs text-muted-foreground">
                    {new Date(c.created_at).toLocaleDateString()}
                  </span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <CampaignWizard open={wizardOpen} onClose={() => setWizardOpen(false)} />
    </div>
  );
}
