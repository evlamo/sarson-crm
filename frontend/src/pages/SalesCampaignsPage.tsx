import { useState, useEffect } from 'react';
import { AddContactsDialog } from '@/components/contacts/AddContactsDialog';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetFooter,
} from '@/components/ui/sheet';
import { Plus, Users, Mail, BarChart3, AlertCircle, Loader2, Search, UserPlus, AlertTriangle } from 'lucide-react';
import { RemoveContactModal } from '@/components/RemoveContactModal';

// TypeScript interfaces
interface SalesCampaign {
  id: string;
  name: string;
  description: string | null;
  status: string;
  contact_count: number;
  email_campaign_count: number;
  created_at: string;
}

interface CampaignContact {
  id: string;
  contact_id: string;
  contact_name: string;
  contact_email: string | null;
  contact_company: string | null;
  status: string;
  master_dnc: boolean;
}

interface EmailCampaign {
  id: string;
  name: string;
  subject: string;
  status: string;
  sent_count: number;
  unique_opens: number;
}

interface Campaign {
  id: string;
  name: string;
  subject: string;
  status: string;
  recipient_count: number;
  sent_count: number;
  unique_opens: number;
  created_at: string;
  sales_campaign_id: string | null;
}

interface CampaignsResponse {
  data: Campaign[];
  total: number;
  page: number;
  per_page: number;
}

interface CampaignStats {
  total_contacts: number;
  active_contacts: number;
  completed_contacts: number;
  no_contacts: number;
  excluded_contacts: number;
  email_campaigns: number;
  completion_rate: number;
  exclusion_rate: number;
}

interface ContactsResponse {
  data: CampaignContact[];
  total: number;
  page: number;
  per_page: number;
}

interface EmailCampaignsResponse {
  data: EmailCampaign[];
  total: number;
  page: number;
  per_page: number;
}

interface SalesCampaignsResponse {
  data: SalesCampaign[];
  total: number;
  page: number;
  per_page: number;
}

interface ContactSearchResult {
  id: string;
  full_name: string;
  email: string | null;
  company: string | null;
  tags: string[];
  master_dnc: boolean;
}

interface ContactSearchResponse {
  data: ContactSearchResult[];
  total: number;
  page: number;
  per_page: number;
}

interface TagItem {
  id: string;
  name: string;
  color?: string;
}

interface ListItem {
  id: string;
  name: string;
  member_count?: number;
}

interface AddContactsResult {
  added: number;
  skipped_dnc: number;
  skipped_existing: number;
  dnc_contacts: string[];
}

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-100 text-green-700 border-green-200',
  paused: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  completed: 'bg-blue-100 text-blue-700 border-blue-200',
};

function LoadingSpinner({ text = 'Loading...' }: { text?: string }) {
  return (
    <div className="flex flex-col items-center justify-center p-8 gap-3">
      <Loader2 className="h-8 w-8 animate-spin text-[#253a52]" />
      <span className="text-sm text-muted-foreground">{text}</span>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  return (
    <Badge variant="outline" className={STATUS_COLORS[status] || 'bg-gray-100 text-gray-700'}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </Badge>
  );
}

function CreateSalesCampaignModal({ open, onClose, onSuccess }: { open: boolean; onClose: () => void; onSuccess: () => void }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [status, setStatus] = useState('active');
  const [error, setError] = useState('');

  const mutation = useMutation({
    mutationFn: async () => {
      const res = await api.post('/sales-campaigns', { name, description, status });
      return res.data;
    },
    onSuccess: () => {
      toast.success('Sales campaign created');
      setName('');
      setDescription('');
      onSuccess();
      onClose();
    },
    onError: () => setError('Failed to create campaign'),
  });

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create Sales Campaign</DialogTitle>
        </DialogHeader>
        <form onSubmit={(e) => { e.preventDefault(); mutation.mutate(); }} className="space-y-4">
          {error && <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 p-2 rounded"><AlertCircle className="h-4 w-4" />{error}</div>}
          <div className="space-y-2">
            <Label htmlFor="name">Campaign Name *</Label>
            <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Q1 2026 Outreach" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Input id="description" value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label>Status</Label>
            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="paused">Paused</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Creating...
                </>
              ) : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function CreateEmailCampaignModal({ 
  open, 
  onClose, 
  onSuccess, 
  salesCampaignId 
}: { 
  open: boolean; 
  onClose: () => void; 
  onSuccess: () => void; 
  salesCampaignId?: string;
}) {
  const [name, setName] = useState('');
  const [subject, setSubject] = useState('');
  const [fromEmail, setFromEmail] = useState('');
  const [fromName, setFromName] = useState('');
  const [error, setError] = useState('');

  const mutation = useMutation({
    mutationFn: async () => {
      const endpoint = salesCampaignId 
        ? `/sales-campaigns/${salesCampaignId}/campaigns`
        : '/campaigns';
      
      const payload = {
        name,
        subject,
        from_email: fromEmail,
        from_name: fromName,
      };
      
      const res = await api.post(endpoint, payload);
      return res.data;
    },
    onSuccess: () => {
      toast.success('Campaign created');
      setName('');
      setSubject('');
      setFromEmail('');
      setFromName('');
      onSuccess();
      onClose();
    },
    onError: (err: any) => {
      const message = err.response?.data?.message || 'Failed to create campaign';
      setError(message);
      toast.error(message);
    },
  });

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create Email Campaign</DialogTitle>
        </DialogHeader>
        <form onSubmit={(e) => { e.preventDefault(); mutation.mutate(); }} className="space-y-4">
          {error && <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 p-2 rounded"><AlertCircle className="h-4 w-4" />{error}</div>}
          <div className="space-y-2">
            <Label htmlFor="name">Campaign Name *</Label>
            <Input 
              id="name" 
              value={name} 
              onChange={(e) => setName(e.target.value)} 
              placeholder="Spring Newsletter"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="subject">Email Subject *</Label>
            <Input 
              id="subject" 
              value={subject} 
              onChange={(e) => setSubject(e.target.value)} 
              placeholder="Spring 2026 Update"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="fromName">From Name *</Label>
            <Input 
              id="fromName" 
              value={fromName} 
              onChange={(e) => setFromName(e.target.value)} 
              placeholder="Sarson Funds"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="fromEmail">From Email *</Label>
            <Input 
              id="fromEmail" 
              value={fromEmail} 
              onChange={(e) => setFromEmail(e.target.value)} 
              placeholder="noreply@sarsonfunds.com"
              type="email"
              required
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={mutation.isPending || !name || !subject || !fromEmail || !fromName}>
              {mutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Creating...
                </>
              ) : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ContactsTab({ campaignId }: { campaignId: string }) {
  const isRestricted = useAuth((s) => s.isRestricted);
  const queryClient = useQueryClient();
  const [selectedContacts, setSelectedContacts] = useState<Set<string>>(new Set());
  const [bulkStatus, setBulkStatus] = useState('');
  const [addDrawerOpen, setAddDrawerOpen] = useState(false);

  const { data, isLoading, isFetching } = useQuery<ContactsResponse>({
    queryKey: ['sales-campaign-contacts', campaignId],
    queryFn: async () => {
      const res = await api.get('/sales-campaigns/' + campaignId + '/contacts', { params: { per_page: 100 } });
      return res.data;
    },
  });

  const updateStatusMutation = useMutation({
    mutationFn: async ({ contactId, status }: { contactId: string; status: string }) => {
      await api.put('/sales-campaigns/' + campaignId + '/contacts/' + contactId, { status });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sales-campaign-contacts', campaignId] });
      toast.success('Status updated');
    },
  });

  const removeContactMutation = useMutation({
    mutationFn: async (contactId: string) => {
      await api.delete('/sales-campaigns/' + campaignId + '/contacts/' + contactId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sales-campaign-contacts', campaignId] });
      queryClient.invalidateQueries({ queryKey: ['sales-campaigns'] });
      toast.success('Contact removed');
    },
  });

  const addContactsMutation = useMutation({
    mutationFn: async (contactIds: string[]) => {
      const res = await api.post(`/sales-campaigns/${campaignId}/contacts/bulk`, {
        contact_ids: contactIds,
        initial_status: 'active',
      });
      return res.data;
    },
    onSuccess: (result) => {
      const messages: string[] = [];
      if (result.added > 0) {
        messages.push(`${result.added} contact${result.added !== 1 ? 's' : ''} added`);
      }
      if (result.skipped_dnc > 0) {
        messages.push(`${result.skipped_dnc} DNC skipped`);
      }
      if (result.skipped_existing > 0) {
        messages.push(`${result.skipped_existing} already in campaign`);
      }
      toast.success(messages.join(', ') || 'Contacts processed');
      queryClient.invalidateQueries({ queryKey: ['sales-campaign-contacts', campaignId] });
      queryClient.invalidateQueries({ queryKey: ['sales-campaigns'] });
    },
    onError: () => {
      toast.error('Failed to add contacts');
    },
  });

  const handleBulkUpdate = async () => {
    if (!bulkStatus || selectedContacts.size === 0) return;
    for (const contactId of selectedContacts) {
      await updateStatusMutation.mutateAsync({ contactId, status: bulkStatus });
    }
    setSelectedContacts(new Set());
    setBulkStatus('');
  };

  const handleAddContacts = (contactIds: string[]) => {
    addContactsMutation.mutate(contactIds);
  };

  const contacts: CampaignContact[] = data?.data || [];

  if (isLoading) {
    return <LoadingSpinner text="Loading contacts..." />;
  }

  return (
    <div className="space-y-4">
      {/* Action bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isFetching && !isLoading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Refreshing...
            </div>
          )}
        </div>
        <Button onClick={() => setAddDrawerOpen(true)}>
          <UserPlus className="h-4 w-4 mr-2" />
          Add Contacts
        </Button>
      </div>

      {selectedContacts.size > 0 && (
        <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
          <span className="text-sm font-medium">{selectedContacts.size} selected</span>
          <Select value={bulkStatus} onValueChange={setBulkStatus}>
            <SelectTrigger className="w-40"><SelectValue placeholder="Set status..." /></SelectTrigger>
            <SelectContent>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="complete">Complete</SelectItem>
              <SelectItem value="no">No</SelectItem>
              <SelectItem value="excluded">Excluded</SelectItem>
            </SelectContent>
          </Select>
          <Button size="sm" onClick={handleBulkUpdate} disabled={!bulkStatus}>Apply</Button>
          <Button size="sm" variant="ghost" onClick={() => setSelectedContacts(new Set())}>Clear</Button>
        </div>
      )}
      
      {contacts.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          <Users className="h-12 w-12 mx-auto mb-3 opacity-30" />
          <p>No contacts yet</p>
          <p className="text-sm mt-1">Click "Add Contacts" to get started</p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10"></TableHead>
              <TableHead>Contact</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Company</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-24">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {contacts.map((cc) => (
              <TableRow key={cc.id} className={cc.master_dnc ? 'opacity-60 bg-red-50/50' : ''}>
                <TableCell>
                  <Checkbox
                    checked={selectedContacts.has(cc.contact_id)}
                    onCheckedChange={() => {
                      const newSet = new Set(selectedContacts);
                      if (newSet.has(cc.contact_id)) newSet.delete(cc.contact_id);
                      else newSet.add(cc.contact_id);
                      setSelectedContacts(newSet);
                    }}
                  />
                </TableCell>
                <TableCell className="font-medium">
                  <div className="flex items-center gap-2">
                    {cc.contact_name}
                    {cc.master_dnc && <Badge variant="destructive" className="text-xs">DNC</Badge>}
                  </div>
                </TableCell>
                <TableCell className="text-muted-foreground">{cc.contact_email || '-'}</TableCell>
                <TableCell className="text-muted-foreground">{cc.contact_company || '-'}</TableCell>
                <TableCell>
                  <Select value={cc.status} onValueChange={(val) => updateStatusMutation.mutate({ contactId: cc.contact_id, status: val })}>
                    <SelectTrigger className="w-28 h-8"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="active">Active</SelectItem>
                      <SelectItem value="complete">Complete</SelectItem>
                      <SelectItem value="no">No</SelectItem>
                      <SelectItem value="excluded">Excluded</SelectItem>
                    </SelectContent>
                  </Select>
                </TableCell>
                <TableCell>
                  {!isRestricted && <Button 
                    variant="ghost" 
                    size="sm" 
                    className="text-red-600" 
                    onClick={() => removeContactMutation.mutate(cc.contact_id)}
                    disabled={removeContactMutation.isPending}
                  >
                    {removeContactMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Remove'}
                  </Button>}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <AddContactsDialog 
        isOpen={addDrawerOpen} 
        onClose={() => setAddDrawerOpen(false)} 
        onAddContacts={handleAddContacts}
      />
    </div>
  );
}

// Add Contacts Drawer Component
function EmailCampaignsTab({ campaignId }: { campaignId: string }) {
  const { data, isLoading, isFetching } = useQuery<EmailCampaignsResponse>({
    queryKey: ['email-campaigns-for-sales', campaignId],
    queryFn: async () => {
      const res = await api.get('/email-campaigns', { params: { sales_campaign_id: campaignId, per_page: 50 } });
      return res.data;
    },
  });

  const campaigns: EmailCampaign[] = data?.data || [];

  if (isLoading) {
    return <LoadingSpinner text="Loading email campaigns..." />;
  }

  return (
    <div className="space-y-4">
      {isFetching && !isLoading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Refreshing...
        </div>
      )}
      {campaigns.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">No email campaigns linked</div>
      ) : (
        campaigns.map((ec) => (
          <Card key={ec.id}>
            <CardContent className="p-4 flex items-center justify-between">
              <div>
                <h4 className="font-medium">{ec.name}</h4>
                <p className="text-sm text-muted-foreground">{ec.subject}</p>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right text-sm">
                  <div className="font-medium">{ec.sent_count} sent</div>
                  <div className="text-muted-foreground">{ec.unique_opens} opens</div>
                </div>
                <StatusBadge status={ec.status} />
              </div>
            </CardContent>
          </Card>
        ))
      )}
    </div>
  );
}

function CampaignsTab({ campaignId }: { campaignId: string }) {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);

  const { data, isLoading, isFetching } = useQuery<CampaignsResponse>({
    queryKey: ['sales-campaign-campaigns', campaignId],
    queryFn: async () => {
      const res = await api.get(`/sales-campaigns/${campaignId}/campaigns`, { params: { per_page: 50 } });
      return res.data;
    },
  });

  const deleteCampaign = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/campaigns/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sales-campaign-campaigns', campaignId] });
      toast.success('Campaign deleted');
    },
    onError: () => toast.error('Failed to delete campaign'),
  });

  const campaigns: Campaign[] = data?.data || [];

  if (isLoading) {
    return <LoadingSpinner text="Loading campaigns..." />;
  }

  return (
    <div className="space-y-4">
      {/* Action bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isFetching && !isLoading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Refreshing...
            </div>
          )}
        </div>
        <Button onClick={() => setCreateOpen(true)} className="bg-[#253a52] hover:bg-[#253a52]/90">
          <Plus className="h-4 w-4 mr-2" />
          New Campaign
        </Button>
      </div>

      {campaigns.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          <Mail className="h-12 w-12 mx-auto mb-3 opacity-30" />
          <p>No campaigns yet</p>
          <p className="text-sm mt-1">Click "New Campaign" to create one</p>
        </div>
      ) : (
        <div className="space-y-2">
          {campaigns.map((campaign) => (
            <Card key={campaign.id} className="hover:shadow-md transition-all">
              <CardContent className="p-4 flex items-center justify-between">
                <div className="flex-1">
                  <h4 className="font-medium">{campaign.name}</h4>
                  <p className="text-sm text-muted-foreground">{campaign.subject}</p>
                  <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                    <span>{campaign.recipient_count} recipient{campaign.recipient_count !== 1 ? 's' : ''}</span>
                    <span>{campaign.sent_count} sent</span>
                    <span>{campaign.unique_opens} opens</span>
                    <span className="text-gray-400">Created {new Date(campaign.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <StatusBadge status={campaign.status} />
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-red-600 hover:text-red-700"
                    onClick={() => deleteCampaign.mutate(campaign.id)}
                    disabled={deleteCampaign.isPending}
                  >
                    {deleteCampaign.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Delete'}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <CreateEmailCampaignModal 
        open={createOpen} 
        onClose={() => setCreateOpen(false)} 
        onSuccess={() => queryClient.invalidateQueries({ queryKey: ['sales-campaign-campaigns', campaignId] })}
        salesCampaignId={campaignId}
      />
    </div>
  );
}

function StatsTab({ campaignId }: { campaignId: string }) {
  const { data, isLoading, isFetching } = useQuery<CampaignStats>({
    queryKey: ['sales-campaign-stats', campaignId],
    queryFn: async () => {
      const res = await api.get('/sales-campaigns/' + campaignId + '/stats');
      return res.data.data as CampaignStats;
    },
  });

  // Fetch linked email campaigns
  const { data: emailData } = useQuery<EmailCampaignsResponse>({
    queryKey: ['email-campaigns-for-stats', campaignId],
    queryFn: async () => {
      const res = await api.get('/email-campaigns', { params: { sales_campaign_id: campaignId, per_page: 10 } });
      return res.data;
    },
  });
  const emailCampaigns: EmailCampaign[] = emailData?.data || [];

  if (isLoading) {
    return <LoadingSpinner text="Loading stats..." />;
  }
  if (!data) return null;

  return (
    <div className="space-y-6">
      {isFetching && !isLoading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Refreshing...
        </div>
      )}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card><CardContent className="p-4 text-center"><div className="text-3xl font-bold text-[#253a52]">{data.total_contacts}</div><div className="text-sm text-muted-foreground">Total</div></CardContent></Card>
        <Card><CardContent className="p-4 text-center"><div className="text-3xl font-bold text-green-600">{data.active_contacts}</div><div className="text-sm text-muted-foreground">Active</div></CardContent></Card>
        <Card><CardContent className="p-4 text-center"><div className="text-3xl font-bold text-blue-600">{data.completed_contacts}</div><div className="text-sm text-muted-foreground">Completed</div></CardContent></Card>
        <Card><CardContent className="p-4 text-center"><div className="text-3xl font-bold text-red-600">{data.no_contacts}</div><div className="text-sm text-muted-foreground">Declined</div></CardContent></Card>
        <Card><CardContent className="p-4 text-center"><div className="text-3xl font-bold">{data.completion_rate}%</div><div className="text-sm text-muted-foreground">Completion</div></CardContent></Card>
        <Card><CardContent className="p-4 text-center"><div className="text-3xl font-bold">{data.exclusion_rate}%</div><div className="text-sm text-muted-foreground">Exclusion</div></CardContent></Card>
        <Card><CardContent className="p-4 text-center"><div className="text-3xl font-bold">{data.excluded_contacts}</div><div className="text-sm text-muted-foreground">Excluded</div></CardContent></Card>
        <Card><CardContent className="p-4 text-center"><div className="text-3xl font-bold">{data.email_campaigns}</div><div className="text-sm text-muted-foreground">Emails</div></CardContent></Card>
      </div>

      {/* Linked Email Campaigns */}
      {emailCampaigns.length > 0 && (
        <div className="space-y-3">
          <h3 className="font-semibold text-sm text-muted-foreground uppercase tracking-wide">Email Campaigns</h3>
          <div className="space-y-2">
            {emailCampaigns.map(ec => (
              <div key={ec.id} className="flex items-center justify-between p-3 border rounded-lg bg-white">
                <div className="min-w-0 flex-1">
                  <span className="font-medium truncate block">{ec.name}</span>
                  <span className="text-xs text-muted-foreground truncate block">{ec.subject}</span>
                </div>
                <div className="flex items-center gap-4 text-sm shrink-0">
                  <div className="text-right">
                    <div className="font-medium">{ec.sent_count.toLocaleString()}</div>
                    <div className="text-xs text-muted-foreground">Sent</div>
                  </div>
                  <div className="text-right">
                    <div className="font-medium text-green-600">{ec.unique_opens.toLocaleString()}</div>
                    <div className="text-xs text-muted-foreground">Opens</div>
                  </div>
                  <div className="text-right">
                    <div className="font-medium text-blue-600">{ec.unique_clicks.toLocaleString()}</div>
                    <div className="text-xs text-muted-foreground">Clicks</div>
                  </div>
                  <StatusBadge status={ec.status} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function SalesCampaignsPage() {
  const queryClient = useQueryClient();
    const [removeModalOpen, setRemoveModalOpen] = useState(false);
  const [removeModalContact, setRemoveModalContact] = useState<{ id: string; name: string } | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'contacts' | 'emails' | 'campaigns' | 'stats'>('contacts');

  useEffect(() => { document.title = 'Sales Campaigns - Sarson Funds CRM'; }, []);

  const { data, isLoading, isFetching } = useQuery<SalesCampaignsResponse>({
    queryKey: ['sales-campaigns'],
    queryFn: async () => {
      const res = await api.get('/sales-campaigns', { params: { per_page: 100 } });
      return res.data;
    },
  });

  const campaigns: SalesCampaign[] = data?.data || [];
  const selectedCampaign = campaigns.find((c) => c.id === selectedId);

  useEffect(() => {
    if (!selectedId && campaigns.length > 0) setSelectedId(campaigns[0].id);
  }, [campaigns, selectedId]);

  const tabClass = (tab: string) =>
    'px-4 py-2 text-sm font-medium border-b-2 transition-colors ' +
    (activeTab === tab
      ? 'border-[#253a52] text-[#253a52]'
      : 'border-transparent text-muted-foreground hover:text-foreground');

  return (
    <div className="h-[calc(100vh-4rem)] flex">
      <div className="w-80 border-r bg-muted/30 flex flex-col">
        <div className="p-4 border-b flex items-center justify-between">
          <h2 className="font-semibold text-lg">Sales Campaigns</h2>
          <Button size="sm" onClick={() => setCreateOpen(true)}><Plus className="h-4 w-4 mr-1" />New</Button>
        </div>
        <div className="flex-1 overflow-auto p-2 space-y-2">
          {isLoading ? (
            <LoadingSpinner text="Loading campaigns..." />
          ) : campaigns.length === 0 ? (
            <div className="p-4 text-center text-muted-foreground">No campaigns</div>
          ) : (
            <>
              {isFetching && !isLoading && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground px-2 py-1">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Refreshing...
                </div>
              )}
              {campaigns.map((c) => (
                <Card
                  key={c.id}
                  className={'cursor-pointer transition-all hover:shadow-md ' + (selectedId === c.id ? 'ring-2 ring-[#253a52] bg-white' : 'bg-white/80')}
                  onClick={() => setSelectedId(c.id)}
                >
                  <CardContent className="p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <h3 className="font-medium text-sm truncate">{c.name}</h3>
                        <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                          <span className="flex items-center gap-1"><Users className="h-3 w-3" />{c.contact_count}</span>
                          <span className="flex items-center gap-1"><Mail className="h-3 w-3" />{c.email_campaign_count}</span>
                        </div>
                      </div>
                      <StatusBadge status={c.status} />
                    </div>
                  </CardContent>
                </Card>
              ))}
            </>
          )}
        </div>
      </div>

      <div className="flex-1 flex flex-col overflow-hidden">
        {selectedCampaign ? (
          <>
            <div className="p-4 border-b bg-white">
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-xl font-semibold text-[#253a52]">{selectedCampaign.name}</h1>
                  {selectedCampaign.description && <p className="text-sm text-muted-foreground mt-1">{selectedCampaign.description}</p>}
                </div>
                <StatusBadge status={selectedCampaign.status} />
              </div>
              <div className="flex gap-1 mt-4 border-b">
                <button className={tabClass('contacts')} onClick={() => setActiveTab('contacts')}><Users className="h-4 w-4 inline mr-1.5" />Contacts</button>
                <button className={tabClass('campaigns')} onClick={() => setActiveTab('campaigns')}><Mail className="h-4 w-4 inline mr-1.5" />Campaigns</button>
                <button className={tabClass('emails')} onClick={() => setActiveTab('emails')}><Mail className="h-4 w-4 inline mr-1.5" />Email Campaigns</button>
                <button className={tabClass('stats')} onClick={() => setActiveTab('stats')}><BarChart3 className="h-4 w-4 inline mr-1.5" />Stats</button>
              </div>
            </div>
            <div className="flex-1 overflow-auto p-4">
              {activeTab === 'contacts' && <ContactsTab campaignId={selectedCampaign.id} />}
              {activeTab === 'campaigns' && <CampaignsTab campaignId={selectedCampaign.id} />}
              {activeTab === 'emails' && <EmailCampaignsTab campaignId={selectedCampaign.id} />}
              {activeTab === 'stats' && <StatsTab campaignId={selectedCampaign.id} />}
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            {isLoading ? <LoadingSpinner text="Loading..." /> : 'Select a campaign'}
          </div>
        )}
      </div>

      <CreateSalesCampaignModal open={createOpen} onClose={() => setCreateOpen(false)} onSuccess={() => queryClient.invalidateQueries({ queryKey: ['sales-campaigns'] })} />
      {removeModalContact && <RemoveContactModal open={removeModalOpen} onClose={() => { setRemoveModalOpen(false); setRemoveModalContact(null); }} campaignId={selectedCampaign?.id || ""} contactId={removeModalContact.id} contactName={removeModalContact.name} onSuccess={() => { queryClient.invalidateQueries({ queryKey: ["sales-campaign-contacts", selectedCampaign?.id] }); queryClient.invalidateQueries({ queryKey: ["sales-campaigns"] }); setRemoveModalOpen(false); setRemoveModalContact(null); }} />}
    </div>
  );
}

// Add RemoveContactModal insertion after CreateCampaignModal
