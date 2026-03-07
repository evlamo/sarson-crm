import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { formatDate } from '@/lib/formatDate';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

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

export default function CampaignStatsPage() {
  useEffect(() => { document.title = 'Campaign Stats — Sarson Funds CRM'; }, []);

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
  const isDemo = source === 'demo';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">📊 Campaign Stats</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Email campaign performance overview</p>
        </div>
        <Badge variant={isDemo ? 'secondary' : 'default'} className="text-xs">
          {isDemo ? '🧪 Demo Data' : '🟢 Live (Mailchimp)'}
        </Badge>
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
                      <TableRow key={c.id}>
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
