import { useState } from 'react';
import type { AuditLogEntry, FieldHistoryEntry } from '@/lib/auditApi';
import { fetchContactAuditLogs, fetchContactFieldHistory, revertContactField } from '@/lib/auditApi';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { formatDistanceToNow } from 'date-fns';
import { History, RotateCcw, ChevronDown, ChevronUp, User, Clock } from 'lucide-react';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

interface Props {
  contactId: string;
  isAdmin?: boolean;
}

function formatAction(action: string): string {
  const actionMap: Record<string, string> = {
    'contact.create': 'Created',
    'contact.update': 'Updated',
    'contact.delete': 'Deleted',
    'contact.add_tag': 'Added tag',
    'contact.remove_tag': 'Removed tag',
    'contact.revert_field': 'Reverted field',
    'contact.bulk_update': 'Bulk updated',
  };
  return actionMap[action] || action.replace(/^contact\./, '').replace(/_/g, ' ');
}

function formatFieldName(field: string): string {
  return field
    .replace(/_/g, ' ')
    .replace(/\bid\b/gi, 'ID')
    .replace(/^./, (c) => c.toUpperCase());
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function AuditLogItem({ entry }: { entry: AuditLogEntry }) {
  const [expanded, setExpanded] = useState(false);
  const hasChanges = entry.old_values || entry.new_values;

  return (
    <div className="border-b last:border-b-0 py-3">
      <div
        className="flex items-start gap-3 cursor-pointer"
        onClick={() => hasChanges && setExpanded(!expanded)}
      >
        <div className="mt-1 shrink-0 h-7 w-7 rounded-full bg-primary/10 flex items-center justify-center">
          <History className="h-3.5 w-3.5 text-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium">{formatAction(entry.action)}</span>
            {entry.user_name && (
              <span className="text-xs text-muted-foreground">by {entry.user_name}</span>
            )}
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground mt-0.5">
            <Clock className="h-3 w-3" />
            {formatDistanceToNow(new Date(entry.created_at), { addSuffix: true })}
          </div>
        </div>
        {hasChanges && (
          <button className="text-muted-foreground hover:text-foreground">
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        )}
      </div>
      {expanded && hasChanges && (
        <div className="mt-2 ml-10 text-xs bg-muted/50 rounded-lg p-3 space-y-1">
          {Object.keys(entry.new_values || entry.old_values || {}).map((field) => {
            const oldVal = entry.old_values?.[field];
            const newVal = entry.new_values?.[field];
            return (
              <div key={field} className="flex gap-2">
                <span className="font-medium text-muted-foreground min-w-[100px]">{formatFieldName(field)}:</span>
                {oldVal !== undefined && (
                  <span className="text-red-600 line-through">{formatValue(oldVal)}</span>
                )}
                {oldVal !== undefined && newVal !== undefined && <span>→</span>}
                {newVal !== undefined && (
                  <span className="text-green-600">{formatValue(newVal)}</span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function FieldHistoryItem({
  entry,
  isAdmin,
  onRevert,
}: {
  entry: FieldHistoryEntry;
  isAdmin: boolean;
  onRevert: (fieldName: string, targetValue: string | null) => void;
}) {
  return (
    <div className="border-b last:border-b-0 py-3">
      <div className="flex items-start gap-3">
        <div className="mt-1 shrink-0 h-7 w-7 rounded-full bg-blue-500/10 flex items-center justify-center">
          <User className="h-3.5 w-3.5 text-blue-500" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-sm">{formatFieldName(entry.field_name)}</span>
            <span className="text-xs text-muted-foreground">
              {entry.source === 'revert' ? '(reverted)' : ''}
            </span>
          </div>
          <div className="text-sm mt-1">
            <span className="text-red-600 line-through">{entry.old_value || '—'}</span>
            <span className="mx-2">→</span>
            <span className="text-green-600">{entry.new_value || '—'}</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground mt-1">
            <Clock className="h-3 w-3" />
            {formatDistanceToNow(new Date(entry.changed_at), { addSuffix: true })}
            {entry.changed_by_name && <span>by {entry.changed_by_name}</span>}
          </div>
        </div>
        {isAdmin && entry.old_value !== entry.new_value && (
          <Button
            size="sm"
            variant="ghost"
            className="text-xs h-7 px-2"
            onClick={() => onRevert(entry.field_name, entry.old_value)}
          >
            <RotateCcw className="h-3 w-3 mr-1" />
            Revert
          </Button>
        )}
      </div>
    </div>
  );
}

export function ContactActivityPanel({ contactId, isAdmin = false }: Props) {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'activity' | 'history'>('activity');

  const { data: auditLogs, isLoading: logsLoading } = useQuery({
    queryKey: ['contact-audit-logs', contactId],
    queryFn: () => fetchContactAuditLogs(contactId),
  });

  const { data: fieldHistory, isLoading: historyLoading } = useQuery({
    queryKey: ['contact-field-history', contactId],
    queryFn: () => fetchContactFieldHistory(contactId),
    enabled: activeTab === 'history',
  });

  const revertMutation = useMutation({
    mutationFn: ({ fieldName, targetValue }: { fieldName: string; targetValue: string | null }) =>
      revertContactField(contactId, fieldName, targetValue),
    onSuccess: (data) => {
      toast.success(`Reverted ${formatFieldName(data.field)}`);
      queryClient.invalidateQueries({ queryKey: ['contact', contactId] });
      queryClient.invalidateQueries({ queryKey: ['contact-audit-logs', contactId] });
      queryClient.invalidateQueries({ queryKey: ['contact-field-history', contactId] });
    },
    onError: () => {
      toast.error('Failed to revert field');
    },
  });

  const handleRevert = (fieldName: string, targetValue: string | null) => {
    if (confirm(`Revert ${formatFieldName(fieldName)} to "${targetValue || '(empty)'}"?`)) {
      revertMutation.mutate({ fieldName, targetValue });
    }
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-widest flex items-center gap-2">
          <History className="h-4 w-4" />
          Activity & History
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'activity' | 'history')}>
          <TabsList className="grid w-full grid-cols-2 mb-4">
            <TabsTrigger value="activity">Activity</TabsTrigger>
            <TabsTrigger value="history">Field History</TabsTrigger>
          </TabsList>

          <TabsContent value="activity" className="max-h-[400px] overflow-y-auto">
            {logsLoading ? (
              <div className="space-y-3 animate-pulse">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-12 bg-muted rounded" />
                ))}
              </div>
            ) : !auditLogs?.data?.length ? (
              <div className="text-center py-8 text-muted-foreground">
                <History className="h-8 w-8 mx-auto opacity-40 mb-2" />
                <p className="text-sm">No activity yet</p>
              </div>
            ) : (
              auditLogs.data.map((entry) => <AuditLogItem key={entry.id} entry={entry} />)
            )}
          </TabsContent>

          <TabsContent value="history" className="max-h-[400px] overflow-y-auto">
            {historyLoading ? (
              <div className="space-y-3 animate-pulse">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-12 bg-muted rounded" />
                ))}
              </div>
            ) : !fieldHistory?.data?.length ? (
              <div className="text-center py-8 text-muted-foreground">
                <Clock className="h-8 w-8 mx-auto opacity-40 mb-2" />
                <p className="text-sm">No field changes recorded</p>
              </div>
            ) : (
              fieldHistory.data.map((entry) => (
                <FieldHistoryItem
                  key={entry.id}
                  entry={entry}
                  isAdmin={isAdmin}
                  onRevert={handleRevert}
                />
              ))
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}

export default ContactActivityPanel;
