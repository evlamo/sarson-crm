import { useAuth } from "@/hooks/useAuth";
import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { formatDateTime } from '@/lib/formatDate';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Trash2, Upload, ChevronDown, ChevronRight } from 'lucide-react';

interface ImportJob {
  id: string;
  filename: string;
  status: string;
  created: number;
  updated: number;
  skipped: number;
  error_count: number;
  total_rows: number | null;
  errors: { row?: number; message?: string }[] | null;
  created_at: string;
}

const STATUS_STYLES: Record<string, string> = {
  complete: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  completed: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  failed: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  processing: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
};

export default function ImportHistoryPage() {
  const queryClient = useQueryClient();
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => { document.title = 'Import History — Sarson Funds CRM'; }, []);

  const { data: imports = [], isLoading } = useQuery<ImportJob[]>({
    queryKey: ['imports'],
    queryFn: async () => {
      const res = await api.get('/imports');
      return Array.isArray(res.data) ? res.data : res.data.data || [];
    },
  });

  const isRestricted = useAuth((s) => s.isRestricted);
  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/imports/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['imports'] });
    },
  });

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold">Import History</h1>
        <p className="text-sm text-muted-foreground mt-0.5">View past CSV import jobs</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="h-4 w-4" />
            Imports ({imports.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-14 bg-muted rounded animate-pulse" />
              ))}
            </div>
          ) : imports.length === 0 ? (
            <div className="text-center py-12">
              <Upload className="h-8 w-8 mx-auto text-muted-foreground/40 mb-2" />
              <p className="text-sm text-muted-foreground">No imports yet</p>
            </div>
          ) : (
            <div className="divide-y">
              {imports.map((job) => {
                const isExpanded = expandedId === job.id;
                const hasErrors = job.errors && job.errors.length > 0;
                const statusStyle = STATUS_STYLES[job.status] || STATUS_STYLES.pending;

                return (
                  <div key={job.id} className="py-3">
                    <div
                      className="flex items-center justify-between cursor-pointer"
                      onClick={() => hasErrors ? setExpandedId(isExpanded ? null : job.id) : undefined}
                    >
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        {hasErrors ? (
                          isExpanded ? <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                        ) : (
                          <span className="w-4" />
                        )}
                        <div className="min-w-0">
                          <p className="text-sm font-medium truncate">{job.filename || 'Unnamed import'}</p>
                          <p className="text-xs text-muted-foreground">
                            {formatDateTime(job.created_at)}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="text-xs text-muted-foreground text-right space-x-3">
                          {job.created > 0 && <span className="text-green-600">{job.created} created</span>}
                          {job.skipped > 0 && <span>{job.skipped} skipped</span>}
                          {job.error_count > 0 && <span className="text-red-600">{job.error_count} errors</span>}
                        </div>
                        <Badge className={`text-xs ${statusStyle}`} variant="secondary">
                          {job.status}
                        </Badge>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                          onClick={(e) => { e.stopPropagation(); deleteMutation.mutate(job.id); }} style={{ display: isRestricted ? "none" : undefined }}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>
                    {isExpanded && hasErrors && (
                      <div className="mt-2 ml-7 p-3 bg-red-50 dark:bg-red-950/20 rounded text-xs space-y-1 max-h-48 overflow-y-auto">
                        {(job.errors || []).map((err, i) => (
                          <p key={i} className="text-red-700 dark:text-red-300">
                            {err.row != null && <span className="font-medium">Row {err.row}: </span>}
                            {err.message || JSON.stringify(err)}
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
