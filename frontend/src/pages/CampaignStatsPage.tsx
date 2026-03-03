import { useEffect, useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '@/lib/api';
import { formatDate } from '@/lib/formatDate';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
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
} from '@/components/ui/sheet';

interface CampaignStat {
  id: string;
  name: string;
  send_date: string | null;
  recipients: number;
  delivered: number;
  opens: number;
  clicks: number;
  unsubscribes: number;
  bounces: number;
  open_rate: number;
  click_rate: number;
  unsubscribe_rate: number;
  bounce_rate: number;
  status: string;
}

interface SalesCampaignOption {
  id: string;
  name: string;
}

interface CampaignSummary {
  total_sent: number;
  delivered_rate: number;
  open_rate: number;
  click_rate: number;
  unsubscribe_rate: number;
  bounce_rate: number;
  source: string;
}

interface CampaignStatsResponse {
  campaigns: CampaignStat[];
  source: string;
  sales_campaigns: SalesCampaignOption[];
}

interface UnsubscriberRecord {
  email: string;
  contact_id: string | null;
  contact_name: string | null;
  reason: string | null;
}

interface CampaignDetail {
  campaign_id: string;
  name: string;
  subject: string | null;
  status: string;
  send_date: string | null;
  sales_campaign_id: string | null;
  sales_campaign_name: string | null;
  sent: number;
  delivered: number;
  opens: number;
  unique_opens: number;
  clicks: number;
  unique_clicks: number;
  unsubscribes: number;
  bounces: number;
  open_rate: number;
  click_rate: number;
  unsubscribe_rate: number;
  bounce_rate: number;
  unsubscribers: UnsubscriberRecord[];
  mailchimp_required: boolean;
}

const STATUS_STYLES: Record<string, string> = {
  sent: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  sending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  draft: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300',
  paused: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
  schedule: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
};

function KPICard({ label, value, suffix }: { label: string; value: string | number; suffix?: string }) {
  return (
    <Card>
      <CardContent className="pt-6 pb-4">
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
        <p className="text-3xl font-bold mt-1">
          {value}{suffix && <span className="text-lg font-normal text-muted-foreground">{suffix}</span>}
        </p>
      </CardContent>
    </Card>
  );
}

function StatCard({ label, value, sub }: { label: string; value: number; sub?: string }) {
  return (
    <div className="bg-muted/50 rounded-lg p-3 text-center">
      <div className="text-2xl font-bold">{value.toLocaleString()}</div>
      {sub && <div className="text-sm font-medium text-muted-foreground">{sub}</div>}
      <div className="text-xs text-muted-foreground mt-1">{label}</div>
    </div>
  );
}

function CampaignDetailDrawer({ campaignId, onClose }: { campaignId: string; onClose: () => void }) {
  const { data, isLoading } = useQuery<CampaignDetail>({
    queryKey: ['campaign-detail', campaignId],
    queryFn: () => api.get(`/campaign-stats/${campaignId}/detail`).then(r => r.data),
    enabled: !!campaignId,
  });

  const dncMutation = useMutation({
    mutationFn: ({ contactId, reason }: { contactId: string; reason: string }) =>
      api.post(`/contacts/${contactId}/dnc`, { reason }),
    onSuccess: () => toast.success('Contact marked as Do Not Contact'),
    onError: () => toast.error('Failed to set DNC'),
  });

  const statusClass = data?.status ? (STATUS_STYLES[data.status] || STATUS_STYLES.draft) : '';

  return (
    <Sheet open={!!campaignId} onOpenChange={() => onClose()}>
      <SheetContent className="w-full sm:max-w-xl overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            {data?.name || 'Campaign Detail'}
            {data?.status && (
              <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium capitalize ${statusClass}`}>
                {data.status}
              </span>
            )}
          </SheetTitle>
          {data?.sales_campaign_name && (
            <p className="text-sm text-muted-foreground">Part of: {data.sales_campaign_name}</p>
          )}
          {data?.send_date && (
            <p className="text-sm text-muted-foreground">Sent: {data.send_date}</p>
          )}
        </SheetHeader>

        {isLoading ? (
          <div className="mt-4 space-y-3">
            {[1, 2, 3].map(i => <div key={i} className="h-16 bg-muted rounded animate-pulse" />)}
          </div>
        ) : data ? (
          <div className="space-y-6 mt-4">
            {/* Stat cards */}
            <div className="grid grid-cols-3 gap-3">
              <StatCard label="Sent" value={data.sent} />
              <StatCard label="Opens" value={data.unique_opens} sub={`${data.open_rate}%`} />
              <StatCard label="Clicks" value={data.unique_clicks} sub={`${data.click_rate}%`} />
              <StatCard label="Delivered" value={data.delivered} />
              <StatCard label="Unsubscribes" value={data.unsubscribes} />
              <StatCard label="Bounces" value={data.bounces} />
            </div>

            {/* Unsubscribers */}
            <div>
              <h3 className="font-medium mb-3">Unsubscribers</h3>
              {data.mailchimp_required ? (
                <p className="text-sm text-muted-foreground">Connect Mailchimp to see individual unsubscribers</p>
              ) : data.unsubscribers.length === 0 ? (
                <p className="text-sm text-muted-foreground">No unsubscribes from this campaign</p>
              ) : (
                <div className="space-y-0">
                  {data.unsubscribers.map((u, i) => (
                    <div key={i} className="flex items-center justify-between py-2 border-b last:border-0">
                      <div>
                        <p className="text-sm font-medium">{u.contact_name || u.email}</p>
                        {u.contact_name && <p className="text-xs text-muted-foreground">{u.email}</p>}
                        {!u.contact_id && <p className="text-xs text-muted-foreground">Not in CRM</p>}
                      </div>
                      {u.contact_id && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-red-600 border-red-200 hover:bg-red-50"
                          onClick={() => dncMutation.mutate({
                            contactId: u.contact_id!,
                            reason: `Unsubscribed via ${data.name}`
                          })}
                          disabled={dncMutation.isPending}
                        >
                          Set DNC
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

export default function CampaignStatsPage() {
  useEffect(() => { document.title = 'Campaign Stats — Sarson Funds CRM'; }, []);
  
  const [detailCampaignId, setDetailCampaignId] = useState<string | null>(null);

  const { data: summary, isLoading: summaryLoading, isError: summaryError } = useQuery<CampaignSummary>({
    queryKey: ['campaign-stats-summary'],
    queryFn: async () => {
      const res = await api.get<CampaignSummary>('/campaign-stats/summary');
      return res.data;
    },
  });

  const { data: statsData, isLoading: statsLoading, isError: statsError } = useQuery<CampaignStatsResponse>({
    queryKey: ['campaign-stats'],
    queryFn: async () => {
      const res = await api.get<CampaignStatsResponse>('/campaign-stats');
      return res.data;
    },
  });

  const source = summary?.source || statsData?.source || 'demo';
  const campaigns = statsData?.campaigns || [];
  const salesCampaigns = statsData?.sales_campaigns || [];
  const isDemo = source === 'demo';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold">📊 Campaign Stats</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Email campaign performance overview</p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={salesCampaignFilter} onValueChange={setSalesCampaignFilter}>
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="Filter by Sales Campaign" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Campaigns</SelectItem>
              <SelectItem value="standalone">Standalone Only</SelectItem>
              {salesCampaigns.map(sc => (
                <SelectItem key={sc.id} value={sc.id}>{sc.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Badge variant={isDemo ? 'secondary' : 'default'} className="text-xs">
            {isDemo ? '🧪 Demo Data' : source === 'crm' ? '📂 CRM Data' : '🟢 Live (Mailchimp)'}
          </Badge>
        </div>
      </div>

      {(summaryError || statsError) && (
        <Card className="border-red-300 bg-red-50 dark:bg-red-950/30 dark:border-red-800">
          <CardContent className="pt-4 pb-4">
            <p className="text-sm text-red-800 dark:text-red-200">
              ❌ Failed to load campaign stats. Please try again later.
            </p>
          </CardContent>
        </Card>
      )}

      {isDemo && (
        <div className="rounded-lg border border-yellow-300 bg-yellow-50 dark:bg-yellow-950/30 dark:border-yellow-800 px-4 py-3">
          <p className="text-sm text-yellow-800 dark:text-yellow-200">
            ⚠️ <strong>Showing Demo Data</strong> — Connect Mailchimp to view live Sarson Funds campaign stats
          </p>
        </div>
      )}

      {/* KPI Cards */}
      {summaryLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {[1, 2, 3, 4, 5, 6].map(i => (
            <Card key={i}><CardContent className="pt-6 pb-4"><div className="h-12 bg-muted rounded animate-pulse" /></CardContent></Card>
          ))}
        </div>
      ) : summary && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <KPICard label="Total Sent" value={summary.total_sent.toLocaleString()} />
          <KPICard label="Delivered Rate" value={summary.delivered_rate} suffix="%" />
          <KPICard label="Open Rate" value={summary.open_rate} suffix="%" />
          <KPICard label="Click Rate" value={summary.click_rate} suffix="%" />
          <KPICard label="Unsub Rate" value={summary.unsubscribe_rate} suffix="%" />
          <KPICard label="Bounce Rate" value={summary.bounce_rate} suffix="%" />
        </div>
      )}

      {/* Performance Sparkline Table */}
      <Card>
        <CardHeader>
          <CardTitle>Campaign Performance</CardTitle>
        </CardHeader>
        <CardContent>
          {statsLoading ? (
            <div className="space-y-3">
              {[1, 2, 3, 4].map(i => <div key={i} className="h-10 bg-muted rounded animate-pulse" />)}
            </div>
          ) : campaigns.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">No campaigns found.</p>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/40">
                    <TableHead className="text-xs font-semibold uppercase">Campaign</TableHead>
                    <TableHead className="text-xs font-semibold uppercase">Sales Campaign</TableHead>
                    <TableHead className="text-xs font-semibold uppercase">Send Date</TableHead>
                    <TableHead className="text-xs font-semibold uppercase text-right">Recipients</TableHead>
                    <TableHead className="text-xs font-semibold uppercase text-right">Open Rate</TableHead>
                    <TableHead className="text-xs font-semibold uppercase text-right">Click Rate</TableHead>
                    <TableHead className="text-xs font-semibold uppercase text-right">Unsub Rate</TableHead>
                    <TableHead className="text-xs font-semibold uppercase">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {campaigns.map((c) => {
                    const statusClass = STATUS_STYLES[c.status] || STATUS_STYLES.draft;
                    return (
                      <TableRow 
                        key={c.id} 
                        className="cursor-pointer hover:bg-muted/50 transition-colors"
                        onClick={() => setDetailCampaignId(c.id)}
                      >
                        <TableCell className="font-medium max-w-[280px] truncate">{c.name}</TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {c.send_date ? formatDate(c.send_date + 'T00:00:00') : '—'}
                        </TableCell>
                        <TableCell className="text-right">{c.recipients.toLocaleString()}</TableCell>
                        <TableCell className="text-right">
                          <span className="inline-flex items-center gap-1">
                            {c.open_rate > 0 && <MiniBar pct={c.open_rate} max={40} color="bg-green-500" />}
                            {c.open_rate}%
                          </span>
                        </TableCell>
                        <TableCell className="text-right">
                          <span className="inline-flex items-center gap-1">
                            {c.click_rate > 0 && <MiniBar pct={c.click_rate} max={10} color="bg-blue-500" />}
                            {c.click_rate}%
                          </span>
                        </TableCell>
                        <TableCell className="text-right">{c.unsubscribe_rate}%</TableCell>
                        <TableCell>
                          <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium capitalize ${statusClass}`}>
                            {c.status}
                          </span>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Detail Drawer */}
      {detailCampaignId && (
        <CampaignDetailDrawer 
          campaignId={detailCampaignId} 
          onClose={() => setDetailCampaignId(null)} 
        />
      )}
    </div>
  );
}

/** Tiny inline bar for visual comparison */
function MiniBar({ pct, max, color }: { pct: number; max: number; color: string }) {
  const width = Math.min((pct / max) * 100, 100);
  return (
    <span className="inline-block w-12 h-2 bg-muted rounded-full overflow-hidden">
      <span className={`block h-full rounded-full ${color}`} style={{ width: `${width}%` }} />
    </span>
  );
}
