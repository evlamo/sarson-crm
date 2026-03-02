import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { formatDistanceToNow, format } from 'date-fns';
import { History, User, Building2, List, Megaphone, Clock, ChevronDown, ChevronUp, Filter, RefreshCw } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { fetchAuditLogs, AuditLogEntry } from '@/lib/auditApi';

const entityIcons: Record<string, typeof User> = {
  contact: User,
  company: Building2,
  list: List,
  campaign: Megaphone,
  sales_campaign: Megaphone,
};

const entityColors: Record<string, string> = {
  contact: 'bg-blue-500/10 text-blue-500',
  company: 'bg-purple-500/10 text-purple-500',
  list: 'bg-green-500/10 text-green-500',
  campaign: 'bg-orange-500/10 text-orange-500',
  sales_campaign: 'bg-orange-500/10 text-orange-500',
};

function formatAction(action: string): string {
  return action
    .replace(/^[a-z_]+\./, '')
    .replace(/_/g, ' ')
    .replace(/^./, (c) => c.toUpperCase());
}

function formatFieldName(field: string): string {
  return field.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function ActivityItem({ entry }: { entry: AuditLogEntry }) {
  const [expanded, setExpanded] = useState(false);
  const hasDetails = entry.old_values || entry.new_values;
  const Icon = entityIcons[entry.entity_type] || History;
  const colorClass = entityColors[entry.entity_type] || 'bg-gray-500/10 text-gray-500';

  return (
    <div className="border-b last:border-b-0 py-4">
      <div
        className={`flex items-start gap-4 ${hasDetails ? 'cursor-pointer' : ''}`}
        onClick={() => hasDetails && setExpanded(!expanded)}
      >
        <div className={`shrink-0 h-10 w-10 rounded-full flex items-center justify-center ${colorClass}`}>
          <Icon className="h-5 w-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="outline" className="text-xs font-normal capitalize">
              {entry.entity_type.replace(/_/g, ' ')}
            </Badge>
            <span className="text-sm font-medium">{formatAction(entry.action)}</span>
          </div>
          <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1">
            {entry.user_name && (
              <span className="flex items-center gap-1">
                <User className="h-3 w-3" />
                {entry.user_name}
              </span>
            )}
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {formatDistanceToNow(new Date(entry.created_at), { addSuffix: true })}
            </span>
            <span className="text-muted-foreground/50">
              {format(new Date(entry.created_at), 'MMM d, yyyy h:mm a')}
            </span>
          </div>
        </div>
        {hasDetails && (
          <button className="text-muted-foreground hover:text-foreground p-1">
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        )}
      </div>
      {expanded && hasDetails && (
        <div className="mt-3 ml-14 text-xs bg-muted/50 rounded-lg p-4">
          <div className="grid gap-2">
            {Object.keys(entry.new_values || entry.old_values || {}).map((field) => {
              const oldVal = entry.old_values?.[field];
              const newVal = entry.new_values?.[field];
              return (
                <div key={field} className="flex gap-2 items-start">
                  <span className="font-medium text-muted-foreground min-w-[120px] shrink-0">
                    {formatFieldName(field)}:
                  </span>
                  <div className="flex gap-2 flex-wrap">
                    {oldVal !== undefined && (
                      <span className="text-red-600 line-through break-all">{formatValue(oldVal)}</span>
                    )}
                    {oldVal !== undefined && newVal !== undefined && <span>→</span>}
                    {newVal !== undefined && (
                      <span className="text-green-600 break-all">{formatValue(newVal)}</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default function ActivityPage() {
  useEffect(() => {
    document.title = 'Activity — Sarson Funds CRM';
  }, []);

  const [entityTypeFilter, setEntityTypeFilter] = useState<string>('all');
  const [page, setPage] = useState(1);

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['audit-logs', entityTypeFilter, page],
    queryFn: () =>
      fetchAuditLogs({
        entity_type: entityTypeFilter === 'all' ? undefined : entityTypeFilter,
        page,
        per_page: 50,
      }),
  });

  return (
    <div className="container max-w-4xl py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Activity Log</h1>
        <p className="text-muted-foreground">Recent changes across contacts, companies, lists, and campaigns</p>
      </div>

      <Card>
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <Select value={entityTypeFilter} onValueChange={(v) => { setEntityTypeFilter(v); setPage(1); }}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Filter by type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value="contact">Contacts</SelectItem>
                  <SelectItem value="company">Companies</SelectItem>
                  <SelectItem value="list">Lists</SelectItem>
                  <SelectItem value="campaign">Campaigns</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button variant="ghost" size="sm" onClick={() => refetch()} disabled={isFetching}>
              <RefreshCw className={`h-4 w-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-4 animate-pulse">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-16 bg-muted rounded" />
              ))}
            </div>
          ) : !data?.data?.length ? (
            <div className="text-center py-12 text-muted-foreground">
              <History className="h-12 w-12 mx-auto opacity-40 mb-3" />
              <p>No activity recorded yet</p>
            </div>
          ) : (
            <>
              {data.data.map((entry) => (
                <ActivityItem key={entry.id} entry={entry} />
              ))}
              
              {/* Pagination */}
              {data.total > data.per_page && (
                <div className="flex items-center justify-between pt-4 border-t mt-4">
                  <span className="text-sm text-muted-foreground">
                    Showing {(page - 1) * data.per_page + 1} - {Math.min(page * data.per_page, data.total)} of {data.total}
                  </span>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page === 1}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => p + 1)}
                      disabled={page * data.per_page >= data.total}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
