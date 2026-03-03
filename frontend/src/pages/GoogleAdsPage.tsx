import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
import { formatDateTime } from '@/lib/formatDate';
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
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';

// ── Types ─────────────────────────────────────────────────────────────────

interface Stats {
  synced_today: number;
  pending: number;
  errors: number;
  total_all_time: number;
  last_sync_at: string | null;
}

interface ConversionRecord {
  id: string;
  contact_id: string | null;
  gclid: string;
  conversion_name: string;
  conversion_value: number | null;
  conversion_time: string;
  sync_status: string;
  error_message: string | null;
  error_code: string | null;
  retry_count: number;
  synced_at: string | null;
  created_at: string;
}

interface TrackedContact {
  id: string;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  status: string | null;
  gclid: string | null;
  gclid_captured_at: string | null;
  gclid_expires_at: string | null;
  conversion_status: string | null;
  conversion_synced_at: string | null;
  conversion_name: string | null;
  conversion_value: number | null;
}

interface ConversionAction {
  id: string;
  name: string;
  google_conversion_action_id: string | null;
  default_value: number;
  trigger_on_status: string | null;
  is_active: boolean;
  created_at: string;
}

interface AuthStatus {
  configured: boolean;
  customer_id: string | null;
  has_developer_token: boolean;
  has_refresh_token: boolean;
}

// ── Helpers ───────────────────────────────────────────────────────────────

function statusBadge(status: string | null) {
  if (!status) return <Badge variant="outline">—</Badge>;
  const map: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-800',
    success: 'bg-green-100 text-green-800',
    synced: 'bg-green-100 text-green-800',
    transient_error: 'bg-orange-100 text-orange-800',
    permanent_error: 'bg-red-100 text-red-800',
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${map[status] || 'bg-gray-100 text-gray-800'}`}>
      {status.replace(/_/g, ' ')}
    </span>
  );
}

function relativeTime(iso: string | null) {
  if (!iso) return 'Never';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

// ── Tabs ──────────────────────────────────────────────────────────────────

type Tab = 'overview' | 'log' | 'contacts' | 'settings';

// ── Main Component ────────────────────────────────────────────────────────

export default function GoogleAdsPage() {
  const { isAdmin } = useAuth();
  const [tab, setTab] = useState<Tab>('overview');

  useEffect(() => {
    document.title = 'Google Ads — Sarson Funds CRM';
  }, []);

  const tabs: { key: Tab; label: string; adminOnly?: boolean }[] = [
    { key: 'overview', label: 'Overview' },
    { key: 'log', label: 'Conversion Log' },
    { key: 'contacts', label: 'Tracked Contacts' },
    { key: 'settings', label: 'Settings', adminOnly: true },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Google Ads</h1>
        <p className="text-muted-foreground text-sm">Offline Conversion Tracking (OCT)</p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b">
        {tabs
          .filter((t) => !t.adminOnly || isAdmin)
          .map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                tab === t.key
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              {t.label}
            </button>
          ))}
      </div>

      {tab === 'overview' && <OverviewTab />}
      {tab === 'log' && <ConversionLogTab />}
      {tab === 'contacts' && <TrackedContactsTab />}
      {tab === 'settings' && isAdmin && <SettingsTab />}
    </div>
  );
}

// ── Tab 1: Overview ───────────────────────────────────────────────────────

function OverviewTab() {
  const { data: stats } = useQuery<Stats>({
    queryKey: ['google-ads-stats'],
    queryFn: () => api.get('/google-ads/stats').then((r) => r.data),
  });

  const { data: recentData } = useQuery<{ data: ConversionRecord[] }>({
    queryKey: ['google-ads-conversions-recent'],
    queryFn: () => api.get('/google-ads/conversions', { params: { per_page: 5 } }).then((r) => r.data),
  });

  const cards = [
    { label: 'Synced Today', value: stats?.synced_today ?? '—' },
    { label: 'Pending', value: stats?.pending ?? '—' },
    { label: 'Errors', value: stats?.errors ?? '—' },
    { label: 'All-Time Total', value: stats?.total_all_time ?? '—' },
  ];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {cards.map((c) => (
          <Card key={c.label}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{c.label}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{c.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <p className="text-sm text-muted-foreground">
        Last sync: {relativeTime(stats?.last_sync_at ?? null)}
      </p>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent Conversions</CardTitle>
        </CardHeader>
        <CardContent>
          {!recentData?.data?.length ? (
            <p className="text-sm text-muted-foreground">No conversions yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-4">Conversion</th>
                    <th className="py-2 pr-4">GCLID</th>
                    <th className="py-2 pr-4">Value</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {recentData.data.map((r) => (
                    <tr key={r.id} className="border-b last:border-0">
                      <td className="py-2 pr-4">{r.conversion_name}</td>
                      <td className="py-2 pr-4 font-mono text-xs">{r.gclid}</td>
                      <td className="py-2 pr-4">{r.conversion_value != null ? `$${r.conversion_value}` : '—'}</td>
                      <td className="py-2 pr-4">{statusBadge(r.sync_status)}</td>
                      <td className="py-2">{relativeTime(r.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ── Tab 2: Conversion Log ─────────────────────────────────────────────────

function ConversionLogTab() {
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery<{ data: ConversionRecord[]; total: number }>({
    queryKey: ['google-ads-conversions', statusFilter, page],
    queryFn: () =>
      api.get('/google-ads/conversions', { params: { status: statusFilter || undefined, page, per_page: 25 } }).then((r) => r.data),
  });

  const filters = [
    { label: 'All', value: '' },
    { label: 'Pending', value: 'pending' },
    { label: 'Synced', value: 'success' },
    { label: 'Error', value: 'permanent_error' },
  ];

  const totalPages = data ? Math.ceil(data.total / 25) : 1;

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {filters.map((f) => (
          <button
            key={f.value}
            onClick={() => { setStatusFilter(f.value); setPage(1); }}
            className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
              statusFilter === f.value
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:bg-accent'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="py-2 pr-4">Conversion</th>
              <th className="py-2 pr-4">GCLID</th>
              <th className="py-2 pr-4">Value</th>
              <th className="py-2 pr-4">Status</th>
              <th className="py-2 pr-4">Error</th>
              <th className="py-2">Synced At</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={6} className="py-8 text-center text-muted-foreground">Loading…</td></tr>
            ) : !data?.data?.length ? (
              <tr><td colSpan={6} className="py-8 text-center text-muted-foreground">No records found.</td></tr>
            ) : (
              data.data.map((r) => (
                <tr key={r.id} className="border-b last:border-0">
                  <td className="py-2 pr-4">{r.conversion_name}</td>
                  <td className="py-2 pr-4 font-mono text-xs">{r.gclid}</td>
                  <td className="py-2 pr-4">{r.conversion_value != null ? `$${r.conversion_value}` : '—'}</td>
                  <td className="py-2 pr-4">{statusBadge(r.sync_status)}</td>
                  <td className="py-2 pr-4 text-xs max-w-[200px] truncate">{r.error_message || '—'}</td>
                  <td className="py-2">{formatDateTime(r.synced_at)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center gap-2 justify-end">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</Button>
          <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next</Button>
        </div>
      )}
    </div>
  );
}

// ── Tab 3: Tracked Contacts ───────────────────────────────────────────────

function TrackedContactsTab() {
  const queryClient = useQueryClient();
  const [showExpired, setShowExpired] = useState(false);
  const [page, setPage] = useState(1);
  const [convertDialog, setConvertDialog] = useState<TrackedContact | null>(null);

  const { data, isLoading } = useQuery<{ data: TrackedContact[]; total: number }>({
    queryKey: ['google-ads-contacts', showExpired, page],
    queryFn: () =>
      api.get('/google-ads/contacts', { params: { expired: showExpired, page, per_page: 25 } }).then((r) => r.data),
  });

  const totalPages = data ? Math.ceil(data.total / 25) : 1;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Switch checked={showExpired} onCheckedChange={setShowExpired} />
        <Label className="text-sm">Show expired GCLIDs</Label>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="py-2 pr-4">Name</th>
              <th className="py-2 pr-4">Email</th>
              <th className="py-2 pr-4">CRM Status</th>
              <th className="py-2 pr-4">GCLID</th>
              <th className="py-2 pr-4">Captured</th>
              <th className="py-2 pr-4">Expires</th>
              <th className="py-2 pr-4">Conv. Status</th>
              <th className="py-2"></th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={8} className="py-8 text-center text-muted-foreground">Loading…</td></tr>
            ) : !data?.data?.length ? (
              <tr><td colSpan={8} className="py-8 text-center text-muted-foreground">No tracked contacts.</td></tr>
            ) : (
              data.data.map((c) => (
                <tr key={c.id} className="border-b last:border-0">
                  <td className="py-2 pr-4">{[c.first_name, c.last_name].filter(Boolean).join(' ') || '—'}</td>
                  <td className="py-2 pr-4">{c.email || '—'}</td>
                  <td className="py-2 pr-4"><Badge variant="outline">{c.status || '—'}</Badge></td>
                  <td className="py-2 pr-4 font-mono text-xs">{c.gclid || '—'}</td>
                  <td className="py-2 pr-4">{formatDateTime(c.gclid_captured_at)}</td>
                  <td className="py-2 pr-4">{formatDateTime(c.gclid_expires_at)}</td>
                  <td className="py-2 pr-4">{statusBadge(c.conversion_status)}</td>
                  <td className="py-2">
                    <Button variant="outline" size="sm" onClick={() => setConvertDialog(c)}>
                      Convert
                    </Button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center gap-2 justify-end">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</Button>
          <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next</Button>
        </div>
      )}

      {convertDialog && (
        <ConvertDialog
          contact={convertDialog}
          onClose={() => setConvertDialog(null)}
          onSuccess={() => {
            setConvertDialog(null);
            queryClient.invalidateQueries({ queryKey: ['google-ads-contacts'] });
            queryClient.invalidateQueries({ queryKey: ['google-ads-stats'] });
          }}
        />
      )}
    </div>
  );
}

// ── Convert Dialog ────────────────────────────────────────────────────────

function ConvertDialog({ contact, onClose, onSuccess }: { contact: TrackedContact; onClose: () => void; onSuccess: () => void }) {
  const [conversionName, setConversionName] = useState('');
  const [conversionValue, setConversionValue] = useState('');

  const { data: actions } = useQuery<ConversionAction[]>({
    queryKey: ['conversion-actions'],
    queryFn: () => api.get('/google-ads/conversion-actions').then((r) => r.data),
  });

  const mutation = useMutation({
    mutationFn: () =>
      api.post(`/google-ads/contacts/${contact.id}/convert`, {
        conversion_name: conversionName,
        conversion_value: conversionValue ? parseFloat(conversionValue) : undefined,
      }),
    onSuccess: () => {
      toast.success('Conversion synced to Google Ads');
      onSuccess();
    },
    onError: (err: { response?: { data?: { detail?: string } } }) => {
      toast.error(err?.response?.data?.detail || 'Failed to sync conversion');
    },
  });

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Convert: {[contact.first_name, contact.last_name].filter(Boolean).join(' ')}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div>
            <Label>Conversion Action</Label>
            <Select value={conversionName} onValueChange={setConversionName}>
              <SelectTrigger><SelectValue placeholder="Select action…" /></SelectTrigger>
              <SelectContent>
                {actions?.filter((a) => a.is_active).map((a) => (
                  <SelectItem key={a.id} value={a.name}>{a.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Value Override (optional)</Label>
            <Input type="number" step="0.01" value={conversionValue} onChange={(e) => setConversionValue(e.target.value)} placeholder="Leave blank for default" />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button disabled={!conversionName || mutation.isPending} onClick={() => mutation.mutate()}>
              {mutation.isPending ? 'Syncing…' : 'Send to Google Ads'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── Tab 4: Settings (Admin Only) ──────────────────────────────────────────

function SettingsTab() {
  return (
    <div className="space-y-8">
      <ConversionActionsSection />
      <Separator />
      <ApiConfigSection />
      <Separator />
      <SnippetSection />
    </div>
  );
}

// ── Conversion Actions ────────────────────────────────────────────────────

function ConversionActionsSection() {
  const queryClient = useQueryClient();
  const [editAction, setEditAction] = useState<ConversionAction | null>(null);
  const [showAdd, setShowAdd] = useState(false);

  const { data: actions } = useQuery<ConversionAction[]>({
    queryKey: ['conversion-actions'],
    queryFn: () => api.get('/google-ads/conversion-actions').then((r) => r.data),
  });

  const isRestricted = useAuth((s) => s.isRestricted);
  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/google-ads/conversion-actions/${id}`),
    onSuccess: () => {
      toast.success('Deleted');
      queryClient.invalidateQueries({ queryKey: ['conversion-actions'] });
    },
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">Conversion Actions</h3>
        <Button size="sm" onClick={() => setShowAdd(true)}>Add Action</Button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="py-2 pr-4">Name</th>
              <th className="py-2 pr-4">Google Action ID</th>
              <th className="py-2 pr-4">Default Value</th>
              <th className="py-2 pr-4">Triggers On</th>
              <th className="py-2 pr-4">Active</th>
              <th className="py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {actions?.map((a) => (
              <tr key={a.id} className="border-b last:border-0">
                <td className="py-2 pr-4 font-medium">{a.name}</td>
                <td className="py-2 pr-4 font-mono text-xs">{a.google_conversion_action_id || '—'}</td>
                <td className="py-2 pr-4">${a.default_value}</td>
                <td className="py-2 pr-4">{a.trigger_on_status || '—'}</td>
                <td className="py-2 pr-4">{a.is_active ? '✓' : '✗'}</td>
                <td className="py-2 flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => setEditAction(a)}>Edit</Button>
                  <Button variant="outline" size="sm" className="text-destructive" onClick={() => { if (confirm('Delete this action?')) deleteMutation.mutate(a.id); }}>Delete</Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {(showAdd || editAction) && (
        <ActionFormDialog
          action={editAction}
          onClose={() => { setShowAdd(false); setEditAction(null); }}
          onSaved={() => {
            setShowAdd(false);
            setEditAction(null);
            queryClient.invalidateQueries({ queryKey: ['conversion-actions'] });
          }}
        />
      )}
    </div>
  );
}

function ActionFormDialog({ action, onClose, onSaved }: { action: ConversionAction | null; onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({
    name: action?.name || '',
    google_conversion_action_id: action?.google_conversion_action_id || '',
    default_value: String(action?.default_value ?? 0),
    trigger_on_status: action?.trigger_on_status || '',
    is_active: action?.is_active ?? true,
  });

  const mutation = useMutation({
    mutationFn: () => {
      const payload = {
        name: form.name,
        google_conversion_action_id: form.google_conversion_action_id || null,
        default_value: parseFloat(form.default_value) || 0,
        trigger_on_status: form.trigger_on_status || null,
        is_active: form.is_active,
      };
      return action
        ? api.patch(`/google-ads/conversion-actions/${action.id}`, payload)
        : api.post('/google-ads/conversion-actions', payload);
    },
    onSuccess: () => { toast.success('Saved'); onSaved(); },
    onError: (err: { response?: { data?: { detail?: string } } }) => toast.error(err?.response?.data?.detail || 'Failed'),
  });

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{action ? 'Edit' : 'Add'} Conversion Action</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 pt-2">
          <div><Label>Name</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div><Label>Google Conversion Action ID</Label><Input value={form.google_conversion_action_id} onChange={(e) => setForm({ ...form, google_conversion_action_id: e.target.value })} placeholder="e.g. 987654321" /></div>
          <div><Label>Default Value ($)</Label><Input type="number" step="0.01" value={form.default_value} onChange={(e) => setForm({ ...form, default_value: e.target.value })} /></div>
          <div><Label>Trigger on CRM Status</Label><Input value={form.trigger_on_status} onChange={(e) => setForm({ ...form, trigger_on_status: e.target.value })} placeholder="e.g. hot, poc" /></div>
          <div className="flex items-center gap-2">
            <Switch checked={form.is_active} onCheckedChange={(v) => setForm({ ...form, is_active: v })} />
            <Label>Active</Label>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button disabled={!form.name || mutation.isPending} onClick={() => mutation.mutate()}>
              {mutation.isPending ? 'Saving…' : 'Save'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── API Configuration ─────────────────────────────────────────────────────

function ApiConfigSection() {
  const { data: authStatus } = useQuery<AuthStatus>({
    queryKey: ['google-ads-auth-status'],
    queryFn: () => api.get('/google-ads/auth/status').then((r) => r.data),
  });

  const testMutation = useMutation({
    mutationFn: () => api.post('/google-ads/auth/test').then((r) => r.data),
    onSuccess: (data: { success?: boolean }) => {
      if (data.connected) toast.success(`Connected: ${data.message}`);
      else toast.error(`Connection failed: ${data.message}`);
    },
    onError: (err: { response?: { data?: { detail?: string } } }) => toast.error(err?.response?.data?.detail || 'Test failed'),
  });

  return (
    <div>
      <h3 className="text-lg font-semibold mb-4">API Configuration</h3>
      <Card>
        <CardContent className="pt-6 space-y-3">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">Customer ID:</span>{' '}
              <span className="font-mono">{authStatus?.customer_id || 'Not set'}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Developer Token:</span>{' '}
              {authStatus?.has_developer_token ? <span className="text-green-600">✓ Set</span> : <span className="text-red-600">✗ Missing</span>}
            </div>
            <div>
              <span className="text-muted-foreground">Refresh Token:</span>{' '}
              {authStatus?.has_refresh_token ? <span className="text-green-600">✓ Set</span> : <span className="text-red-600">✗ Missing</span>}
            </div>
            <div>
              <span className="text-muted-foreground">Status:</span>{' '}
              {authStatus?.configured ? <span className="text-green-600">✓ Configured</span> : <span className="text-yellow-600">⚠ Incomplete</span>}
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Credentials are stored in your <code>.env</code> file. Restart the server after updating.
          </p>
          <Button variant="outline" size="sm" onClick={() => testMutation.mutate()} disabled={testMutation.isPending}>
            {testMutation.isPending ? 'Testing…' : 'Test Connection'}
          </Button>
        </CardContent>
      </Card>

      <details className="mt-4">
        <summary className="cursor-pointer text-sm font-medium text-muted-foreground hover:text-foreground">
          Setup Guide — How to get your Google Ads credentials
        </summary>
        <div className="mt-2 space-y-2 text-sm text-muted-foreground pl-4 border-l-2 border-muted">
          <p><strong>1.</strong> Go to <a href="https://console.cloud.google.com/" target="_blank" rel="noopener noreferrer" className="underline">Google Cloud Console</a> → Create OAuth2 credentials (type: Desktop App or Web App) → Copy Client ID and Client Secret</p>
          <p><strong>2.</strong> Grant the required OAuth2 scope: <code className="bg-muted px-1 rounded">https://www.googleapis.com/auth/adwords</code> → Use <a href="https://developers.google.com/oauthplayground/" target="_blank" rel="noopener noreferrer" className="underline">Google&apos;s OAuth2 Playground</a> to generate a refresh token</p>
          <p><strong>3.</strong> Get your Developer Token: Google Ads account → Tools → API Center → Apply for Basic Access</p>
          <p><strong>4.</strong> Customer ID: Found in the top-right of your Google Ads account (format: XXX-XXX-XXXX)</p>
          <p><strong>5.</strong> Manager Account ID (optional): Only needed if using a Google Ads Manager (MCC) account</p>
        </div>
      </details>
    </div>
  );
}

// ── JS Snippet ────────────────────────────────────────────────────────────

function SnippetSection() {
  const [hiddenFieldId, setHiddenFieldId] = useState('gclid_field');
  const [cookieName, setCookieName] = useState('_sarson_gclid');

  const { data } = useQuery<{ snippet: string }>({
    queryKey: ['google-ads-snippet', hiddenFieldId, cookieName],
    queryFn: () =>
      api.get('/google-ads/snippet', { params: { hidden_field_id: hiddenFieldId, cookie_name: cookieName } }).then((r) => r.data),
  });

  return (
    <div>
      <h3 className="text-lg font-semibold mb-4">JS Tracking Snippet</h3>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <Label>Hidden Field ID</Label>
          <Input value={hiddenFieldId} onChange={(e) => setHiddenFieldId(e.target.value)} />
        </div>
        <div>
          <Label>Cookie Name</Label>
          <Input value={cookieName} onChange={(e) => setCookieName(e.target.value)} />
        </div>
      </div>

      {data?.snippet && (
        <div className="relative">
          <pre className="bg-muted p-4 rounded-lg text-xs overflow-x-auto max-h-[400px] font-mono whitespace-pre-wrap">
            {data.snippet}
          </pre>
          <Button
            variant="outline"
            size="sm"
            className="absolute top-2 right-2"
            onClick={() => { navigator.clipboard.writeText(data.snippet); toast.success('Copied!'); }}
          >
            Copy
          </Button>
        </div>
      )}

      <div className="mt-6 space-y-2 text-sm text-muted-foreground">
        <h4 className="font-semibold text-foreground">Setup Instructions</h4>
        <ol className="list-decimal list-inside space-y-1">
          <li>Add a hidden input to your contact form: <code className="bg-muted px-1 rounded">&lt;input type="hidden" name="gclid" id="{hiddenFieldId}" /&gt;</code></li>
          <li>Paste the snippet above before <code>&lt;/body&gt;</code> on every landing page.</li>
          <li>On form submit, POST the GCLID + email to <code>/api/v1/google-ads/capture</code>.</li>
          <li>The CRM will automatically match the GCLID to the contact and track conversions.</li>
        </ol>
      </div>
    </div>
  );
}
