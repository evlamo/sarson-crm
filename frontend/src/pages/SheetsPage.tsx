import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Sheet,
  FileSpreadsheet,
  Upload,
  Download,
  History,
  Settings,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
  ExternalLink,
  Eye,
  EyeOff,
  RefreshCw,
  Shield,
  ArrowRight,
  Check,
  X,
} from 'lucide-react';

// ── Types ─────────────────────────────────────────────────────────────────

interface SheetsConfig {
  spreadsheet_id: string | null;
  sheet_name: string | null;
  credentials_set: boolean;
  last_tested_at: string | null;
  last_test_status: string | null;
}

interface StaticList {
  id: string;
  name: string;
  member_count: number;
}

interface ExportRecord {
  id: string;
  spreadsheet_id: string;
  spreadsheet_url: string | null;
  sheet_name: string | null;
  contact_count: number | null;
  exported_at: string;
  exported_by_name: string | null;
  sync_status: string | null;
  list_name: string | null;
}

interface ConflictItem {
  contact_id: string;
  contact_name: string;
  field: string;
  crm_value: string;
  sheet_value: string;
}

interface NewContactItem {
  row_index: number;
  email: string | null;
  first_name: string | null;
  last_name: string | null;
  company: string | null;
  raw_data: Record<string, string>;
}

interface OrphanItem {
  sheet_row_index: number;
  contact_id: string;
  email: string | null;
  name: string | null;
}

interface ImportPreview {
  review_id: string;
  new_contacts: NewContactItem[];
  conflicts: ConflictItem[];
  orphans: OrphanItem[];
  unchanged_count: number;
  total_sheet_rows: number;
}

// ── Helper Components ─────────────────────────────────────────────────────

function FieldLabel({ field }: { field: string }) {
  const labels: Record<string, string> = {
    first_name: 'First Name',
    last_name: 'Last Name',
    email: 'Email',
    phone: 'Phone',
    company: 'Company',
    title: 'Title',
    status: 'Status',
    tags: 'Tags',
    lead_source: 'Lead Source',
    notes: 'Notes',
    sarson_rep: 'Sarson Rep',
    city: 'City',
    state: 'State',
    country: 'Country',
    linkedin_url: 'LinkedIn',
    website: 'Website',
  };
  return <span className="font-medium">{labels[field] || field}</span>;
}

function StatusBadge({ status }: { status: string | null }) {
  if (!status) return <Badge variant="secondary">Unknown</Badge>;
  
  const variants: Record<string, { variant: 'default' | 'secondary' | 'destructive' | 'outline'; label: string }> = {
    active: { variant: 'default', label: 'Active' },
    processing: { variant: 'secondary', label: 'Processing' },
    partial: { variant: 'outline', label: 'Partial' },
    error: { variant: 'destructive', label: 'Error' },
    archived: { variant: 'secondary', label: 'Archived' },
  };
  
  const config = variants[status] || { variant: 'secondary', label: status };
  return <Badge variant={config.variant}>{config.label}</Badge>;
}

// ── Export Tab ────────────────────────────────────────────────────────────

function ExportTab({ config }: { config: SheetsConfig | undefined }) {
  const queryClient = useQueryClient();
  const [spreadsheetId, setSpreadsheetId] = useState('');
  const [sheetName, setSheetName] = useState('CRM Export');
  const [selectedList, setSelectedList] = useState<string>('all');

  useEffect(() => {
    if (config?.spreadsheet_id) setSpreadsheetId(config.spreadsheet_id);
    if (config?.sheet_name) setSheetName(config.sheet_name);
  }, [config]);

  const { data: lists } = useQuery<{ data: StaticList[] }>({
    queryKey: ['static-lists'],
    queryFn: async () => {
      const res = await api.get('/lists');
      return res.data;
    },
  });

  const exportMutation = useMutation({
    mutationFn: async () => {
      const payload: Record<string, string | undefined> = {
        spreadsheet_id: spreadsheetId,
        sheet_name: sheetName,
      };
      if (selectedList !== 'all') {
        payload.list_id = selectedList;
      }
      const res = await api.post('/sheets/export', payload);
      return res.data;
    },
    onSuccess: (data) => {
      toast.success(`Exported ${data.rows_written} contacts to Google Sheets`);
      queryClient.invalidateQueries({ queryKey: ['sheets-exports'] });
    },
    onError: (err: Error & { response?: { data?: { detail?: string } } }) => {
      toast.error(err.response?.data?.detail || 'Export failed');
    },
  });

  const isReady = config?.credentials_set && spreadsheetId;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Download className="h-5 w-5" />
            Export to Google Sheets
          </CardTitle>
          <CardDescription>
            Push CRM contacts to a Google Sheet for editing or sharing
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="spreadsheet-id">Spreadsheet ID</Label>
              <Input
                id="spreadsheet-id"
                placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
                value={spreadsheetId}
                onChange={(e) => setSpreadsheetId(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Found in the URL: docs.google.com/spreadsheets/d/<strong>[ID]</strong>/edit
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="sheet-name">Sheet Tab Name</Label>
              <Input
                id="sheet-name"
                placeholder="CRM Export"
                value={sheetName}
                onChange={(e) => setSheetName(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Tab will be created if it doesn't exist
              </p>
            </div>
          </div>

          <div className="space-y-2">
            <Label>Contact Source</Label>
            <Select value={selectedList} onValueChange={setSelectedList}>
              <SelectTrigger className="w-full md:w-64">
                <SelectValue placeholder="Select source" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Contacts</SelectItem>
                {lists?.data?.map((list) => (
                  <SelectItem key={list.id} value={list.id}>
                    {list.name} ({list.member_count.toLocaleString()})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {!config?.credentials_set && (
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-md text-sm text-amber-800 flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
              <div>
                <p className="font-medium">Service account not configured</p>
                <p className="text-xs mt-0.5">Go to Settings tab to add your Google service account credentials</p>
              </div>
            </div>
          )}

          <Button
            onClick={() => exportMutation.mutate()}
            disabled={!isReady || exportMutation.isPending}
            className="w-full md:w-auto"
          >
            {exportMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            <Download className="h-4 w-4 mr-2" />
            Export Contacts
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

// ── Import Tab (Conflict Resolution UI) ───────────────────────────────────

function ImportTab({ config }: { config: SheetsConfig | undefined }) {
  const queryClient = useQueryClient();
  const [spreadsheetId, setSpreadsheetId] = useState('');
  const [sheetName, setSheetName] = useState('CRM Export');
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  
  // Track user decisions
  const [conflictDecisions, setConflictDecisions] = useState<Record<string, 'crm' | 'sheet'>>({});
  const [selectedNewContacts, setSelectedNewContacts] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (config?.spreadsheet_id) setSpreadsheetId(config.spreadsheet_id);
    if (config?.sheet_name) setSheetName(config.sheet_name);
  }, [config]);

  const previewMutation = useMutation({
    mutationFn: async () => {
      const res = await api.post('/sheets/import/preview', {
        spreadsheet_id: spreadsheetId,
        sheet_name: sheetName,
      });
      return res.data as ImportPreview;
    },
    onSuccess: (data) => {
      setPreview(data);
      setConflictDecisions({});
      setSelectedNewContacts(new Set());
      toast.success(`Found ${data.conflicts.length} conflicts, ${data.new_contacts.length} new contacts`);
    },
    onError: (err: Error & { response?: { data?: { detail?: string } } }) => {
      toast.error(err.response?.data?.detail || 'Preview failed');
    },
  });

  const applyMutation = useMutation({
    mutationFn: async () => {
      // Build approved changes from decisions
      const approved_changes: { contact_id: string; field: string; new_value: string }[] = [];
      
      if (preview) {
        for (const conflict of preview.conflicts) {
          const key = `${conflict.contact_id}:${conflict.field}`;
          const decision = conflictDecisions[key];
          if (decision === 'sheet') {
            approved_changes.push({
              contact_id: conflict.contact_id,
              field: conflict.field,
              new_value: conflict.sheet_value,
            });
          }
          // If 'crm' or undefined, we don't apply any change (keep CRM value)
        }
      }

      const res = await api.post('/sheets/import/apply', {
        review_id: preview?.review_id,
        approved_changes,
        import_new_contacts: Array.from(selectedNewContacts),
      });
      return res.data;
    },
    onSuccess: (data) => {
      toast.success(`Applied ${data.changes_applied} changes, created ${data.contacts_created} contacts`);
      if (data.errors.length > 0) {
        toast.warning(`${data.errors.length} errors occurred`);
      }
      setPreview(null);
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
    },
    onError: (err: Error & { response?: { data?: { detail?: string } } }) => {
      toast.error(err.response?.data?.detail || 'Apply failed');
    },
  });

  const setDecisionForConflict = (contactId: string, field: string, decision: 'crm' | 'sheet') => {
    setConflictDecisions((prev) => ({
      ...prev,
      [`${contactId}:${field}`]: decision,
    }));
  };

  const setAllDecisions = (decision: 'crm' | 'sheet') => {
    if (!preview) return;
    const newDecisions: Record<string, 'crm' | 'sheet'> = {};
    for (const conflict of preview.conflicts) {
      newDecisions[`${conflict.contact_id}:${conflict.field}`] = decision;
    }
    setConflictDecisions(newDecisions);
  };

  const toggleNewContact = (rowIndex: number) => {
    setSelectedNewContacts((prev) => {
      const next = new Set(prev);
      if (next.has(rowIndex)) {
        next.delete(rowIndex);
      } else {
        next.add(rowIndex);
      }
      return next;
    });
  };

  const selectAllNew = () => {
    if (!preview) return;
    setSelectedNewContacts(new Set(preview.new_contacts.map((n) => n.row_index)));
  };

  const deselectAllNew = () => {
    setSelectedNewContacts(new Set());
  };

  const pendingSheetChanges = preview ? Object.values(conflictDecisions).filter((d) => d === 'sheet').length : 0;
  const isReady = config?.credentials_set && spreadsheetId;

  return (
    <div className="space-y-6">
      {/* Preview Request Card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Upload className="h-5 w-5" />
            Import from Google Sheets
          </CardTitle>
          <CardDescription>
            Pull changes from a sheet and review before applying
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="import-spreadsheet-id">Spreadsheet ID</Label>
              <Input
                id="import-spreadsheet-id"
                placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
                value={spreadsheetId}
                onChange={(e) => setSpreadsheetId(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="import-sheet-name">Sheet Tab Name</Label>
              <Input
                id="import-sheet-name"
                placeholder="CRM Export"
                value={sheetName}
                onChange={(e) => setSheetName(e.target.value)}
              />
            </div>
          </div>

          <Button
            onClick={() => previewMutation.mutate()}
            disabled={!isReady || previewMutation.isPending}
            variant="outline"
          >
            {previewMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            <RefreshCw className="h-4 w-4 mr-2" />
            Check for Updates
          </Button>
        </CardContent>
      </Card>

      {/* Preview Results */}
      {preview && (
        <div className="space-y-6">
          {/* Summary */}
          <div className="grid gap-4 md:grid-cols-4">
            <Card className="bg-blue-50 border-blue-200">
              <CardContent className="pt-4 text-center">
                <p className="text-2xl font-bold text-blue-700">{preview.total_sheet_rows}</p>
                <p className="text-sm text-blue-600">Sheet Rows</p>
              </CardContent>
            </Card>
            <Card className="bg-amber-50 border-amber-200">
              <CardContent className="pt-4 text-center">
                <p className="text-2xl font-bold text-amber-700">{preview.conflicts.length}</p>
                <p className="text-sm text-amber-600">Conflicts</p>
              </CardContent>
            </Card>
            <Card className="bg-green-50 border-green-200">
              <CardContent className="pt-4 text-center">
                <p className="text-2xl font-bold text-green-700">{preview.new_contacts.length}</p>
                <p className="text-sm text-green-600">New Contacts</p>
              </CardContent>
            </Card>
            <Card className="bg-gray-50 border-gray-200">
              <CardContent className="pt-4 text-center">
                <p className="text-2xl font-bold text-gray-700">{preview.unchanged_count}</p>
                <p className="text-sm text-gray-600">Unchanged</p>
              </CardContent>
            </Card>
          </div>

          {/* Conflicts Section */}
          {preview.conflicts.length > 0 && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5 text-amber-500" />
                    Conflicts ({preview.conflicts.length})
                  </CardTitle>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={() => setAllDecisions('crm')}>
                      Keep All CRM
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setAllDecisions('sheet')}>
                      Use All Sheet
                    </Button>
                  </div>
                </div>
                <CardDescription>
                  These fields have different values in the sheet vs CRM. Choose which value to keep.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[200px]">Contact</TableHead>
                      <TableHead className="w-[120px]">Field</TableHead>
                      <TableHead>CRM Value</TableHead>
                      <TableHead className="w-[50px]"></TableHead>
                      <TableHead>Sheet Value</TableHead>
                      <TableHead className="w-[100px] text-right">Decision</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {preview.conflicts.map((conflict, idx) => {
                      const key = `${conflict.contact_id}:${conflict.field}`;
                      const decision = conflictDecisions[key];
                      return (
                        <TableRow key={idx} className={decision ? 'bg-muted/30' : ''}>
                          <TableCell className="font-medium">{conflict.contact_name}</TableCell>
                          <TableCell><FieldLabel field={conflict.field} /></TableCell>
                          <TableCell 
                            className={`text-sm ${decision === 'crm' ? 'bg-green-50 font-medium' : decision === 'sheet' ? 'line-through text-muted-foreground' : ''}`}
                          >
                            {conflict.crm_value || <span className="text-muted-foreground italic">empty</span>}
                          </TableCell>
                          <TableCell>
                            <ArrowRight className="h-4 w-4 text-muted-foreground" />
                          </TableCell>
                          <TableCell 
                            className={`text-sm ${decision === 'sheet' ? 'bg-blue-50 font-medium' : decision === 'crm' ? 'line-through text-muted-foreground' : ''}`}
                          >
                            {conflict.sheet_value || <span className="text-muted-foreground italic">empty</span>}
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex justify-end gap-1">
                              <Button
                                size="sm"
                                variant={decision === 'crm' ? 'default' : 'outline'}
                                onClick={() => setDecisionForConflict(conflict.contact_id, conflict.field, 'crm')}
                                className="h-7 px-2"
                              >
                                CRM
                              </Button>
                              <Button
                                size="sm"
                                variant={decision === 'sheet' ? 'default' : 'outline'}
                                onClick={() => setDecisionForConflict(conflict.contact_id, conflict.field, 'sheet')}
                                className="h-7 px-2"
                              >
                                Sheet
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          {/* New Contacts Section */}
          {preview.new_contacts.length > 0 && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base flex items-center gap-2">
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                    New Contacts ({preview.new_contacts.length})
                  </CardTitle>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={selectAllNew}>
                      Select All
                    </Button>
                    <Button size="sm" variant="outline" onClick={deselectAllNew}>
                      Deselect All
                    </Button>
                  </div>
                </div>
                <CardDescription>
                  These rows have no ID and appear to be new contacts. Select which to import.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[50px]">Import</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Name</TableHead>
                      <TableHead>Company</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {preview.new_contacts.map((nc) => (
                      <TableRow key={nc.row_index} className={selectedNewContacts.has(nc.row_index) ? 'bg-green-50' : ''}>
                        <TableCell>
                          <Button
                            size="sm"
                            variant={selectedNewContacts.has(nc.row_index) ? 'default' : 'outline'}
                            onClick={() => toggleNewContact(nc.row_index)}
                            className="h-7 w-7 p-0"
                          >
                            {selectedNewContacts.has(nc.row_index) ? (
                              <Check className="h-4 w-4" />
                            ) : (
                              <X className="h-4 w-4" />
                            )}
                          </Button>
                        </TableCell>
                        <TableCell className="font-mono text-sm">{nc.email || '—'}</TableCell>
                        <TableCell>
                          {[nc.first_name, nc.last_name].filter(Boolean).join(' ') || '—'}
                        </TableCell>
                        <TableCell>{nc.company || '—'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          {/* Orphans Warning */}
          {preview.orphans.length > 0 && (
            <Card className="border-red-200 bg-red-50">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2 text-red-700">
                  <XCircle className="h-5 w-5" />
                  Orphaned Rows ({preview.orphans.length})
                </CardTitle>
                <CardDescription className="text-red-600">
                  These rows have IDs that don't exist in CRM (deleted contacts). They will be skipped.
                </CardDescription>
              </CardHeader>
            </Card>
          )}

          {/* Apply Button */}
          <div className="flex items-center justify-between p-4 bg-muted rounded-lg">
            <div>
              <p className="font-medium">Ready to apply?</p>
              <p className="text-sm text-muted-foreground">
                {pendingSheetChanges} field(s) will be updated from sheet, {selectedNewContacts.size} new contact(s) will be created
              </p>
            </div>
            <Button
              onClick={() => applyMutation.mutate()}
              disabled={applyMutation.isPending || (pendingSheetChanges === 0 && selectedNewContacts.size === 0)}
            >
              {applyMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Apply Selected Changes
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── History Tab ───────────────────────────────────────────────────────────

function HistoryTab() {
  const { data: exports, isLoading } = useQuery<ExportRecord[]>({
    queryKey: ['sheets-exports'],
    queryFn: async () => {
      const res = await api.get('/sheets/exports');
      return res.data;
    },
  });

  const relativeTime = (iso: string) => {
    const d = new Date(iso);
    const diff = Date.now() - d.getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'Just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    if (days < 7) return `${days}d ago`;
    return d.toLocaleDateString();
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <History className="h-5 w-5" />
          Export History
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : exports && exports.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Sheet</TableHead>
                <TableHead>Contacts</TableHead>
                <TableHead>List</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>By</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {exports.map((exp) => (
                <TableRow key={exp.id}>
                  <TableCell className="text-sm">{relativeTime(exp.exported_at)}</TableCell>
                  <TableCell className="font-mono text-sm">{exp.sheet_name || '—'}</TableCell>
                  <TableCell>{exp.contact_count?.toLocaleString() || '—'}</TableCell>
                  <TableCell>{exp.list_name || 'All'}</TableCell>
                  <TableCell><StatusBadge status={exp.sync_status} /></TableCell>
                  <TableCell className="text-sm text-muted-foreground">{exp.exported_by_name || '—'}</TableCell>
                  <TableCell>
                    {exp.spreadsheet_url && (
                      <Button size="sm" variant="ghost" asChild>
                        <a href={exp.spreadsheet_url} target="_blank" rel="noopener noreferrer">
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <p className="text-center text-muted-foreground py-8">No exports yet</p>
        )}
      </CardContent>
    </Card>
  );
}

// ── Settings Tab ──────────────────────────────────────────────────────────

function SettingsTab({ config, refetch }: { config: SheetsConfig | undefined; refetch: () => void }) {
  const queryClient = useQueryClient();
  const [spreadsheetId, setSpreadsheetId] = useState('');
  const [sheetName, setSheetName] = useState('CRM Export');
  const [credentialsJson, setCredentialsJson] = useState('');
  const [showCredentials, setShowCredentials] = useState(false);

  useEffect(() => {
    if (config?.spreadsheet_id) setSpreadsheetId(config.spreadsheet_id);
    if (config?.sheet_name) setSheetName(config.sheet_name);
  }, [config]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload: Record<string, string | undefined> = {};
      if (spreadsheetId) payload.spreadsheet_id = spreadsheetId;
      if (sheetName) payload.sheet_name = sheetName;
      if (credentialsJson) payload.credentials_json = credentialsJson;
      const res = await api.post('/sheets/config', payload);
      return res.data;
    },
    onSuccess: () => {
      toast.success('Configuration saved');
      setCredentialsJson('');
      refetch();
      queryClient.invalidateQueries({ queryKey: ['sheets-config'] });
    },
    onError: (err: Error & { response?: { data?: { detail?: string } } }) => {
      toast.error(err.response?.data?.detail || 'Save failed');
    },
  });

  const testMutation = useMutation({
    mutationFn: async () => {
      const res = await api.post('/sheets/test');
      return res.data;
    },
    onSuccess: (data) => {
      if (data.success) {
        toast.success(data.message);
      } else {
        toast.error(data.message);
      }
      refetch();
    },
    onError: () => {
      toast.error('Connection test failed');
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <Settings className="h-5 w-5" />
          Google Sheets Configuration
        </CardTitle>
        <CardDescription>
          Configure your Google service account for Sheets integration
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="settings-spreadsheet-id">Default Spreadsheet ID</Label>
            <Input
              id="settings-spreadsheet-id"
              placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
              value={spreadsheetId}
              onChange={(e) => setSpreadsheetId(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="settings-sheet-name">Default Sheet Tab Name</Label>
            <Input
              id="settings-sheet-name"
              placeholder="CRM Export"
              value={sheetName}
              onChange={(e) => setSheetName(e.target.value)}
            />
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="credentials-json">Service Account JSON</Label>
            {config?.credentials_set && (
              <Badge className="bg-emerald-600 text-white">✓ Configured</Badge>
            )}
          </div>
          <div className="relative">
            <textarea
              id="credentials-json"
              className="w-full h-32 p-3 text-sm font-mono border rounded-md resize-none"
              placeholder={config?.credentials_set 
                ? "Credentials are set. Paste new JSON to replace." 
                : '{"type": "service_account", ...}'}
              value={credentialsJson}
              onChange={(e) => setCredentialsJson(e.target.value)}
              style={{ fontFamily: 'monospace' }}
            />
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="absolute right-2 top-2"
              onClick={() => setShowCredentials(!showCredentials)}
            >
              {showCredentials ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Get this from Google Cloud Console → IAM → Service Accounts → Keys → Add Key → JSON
          </p>
        </div>

        <div className="p-3 bg-blue-50 border border-blue-200 rounded-md text-sm text-blue-800">
          <p className="font-medium">Important: Share your spreadsheet</p>
          <p className="text-xs mt-1">
            After configuring, share your Google Sheet with the service account email 
            (found in the JSON as "client_email") with Editor access.
          </p>
        </div>

        <div className="flex items-center justify-between pt-4 border-t">
          <div className="flex items-center gap-2">
            {config?.last_test_status === 'success' ? (
              <Badge className="bg-emerald-600 text-white">
                <CheckCircle2 className="h-3 w-3 mr-1" />
                Connected
              </Badge>
            ) : config?.last_test_status === 'failed' ? (
              <Badge variant="destructive">
                <XCircle className="h-3 w-3 mr-1" />
                Failed
              </Badge>
            ) : (
              <Badge variant="secondary">Not tested</Badge>
            )}
            {config?.last_tested_at && (
              <span className="text-xs text-muted-foreground">
                Last tested: {new Date(config.last_tested_at).toLocaleString()}
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => testMutation.mutate()} disabled={testMutation.isPending || !config?.credentials_set}>
              {testMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Test Connection
            </Button>
            <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
              {saveMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Save Configuration
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────

export default function SheetsPage() {
  const isAdmin = useAuth((s) => s.isAdmin);

  useEffect(() => {
    document.title = 'Google Sheets Sync — Sarson Funds CRM';
  }, []);

  const { data: config, isLoading, refetch } = useQuery<SheetsConfig>({
    queryKey: ['sheets-config'],
    queryFn: async () => {
      const res = await api.get('/sheets/config');
      return res.data;
    },
    enabled: isAdmin,
  });

  if (!isAdmin) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-muted-foreground">
        <Shield className="h-12 w-12 mb-4" />
        <p className="text-lg font-semibold">Admin Access Required</p>
        <p className="text-sm mt-1">You need admin privileges to manage Google Sheets sync.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-[#0F9D58] flex items-center justify-center">
          <FileSpreadsheet className="h-5 w-5 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Google Sheets Sync</h1>
          <p className="text-sm text-muted-foreground">
            Two-way sync between CRM and Google Sheets
          </p>
        </div>
        <Badge variant="outline" className="ml-2 text-xs">Admin only</Badge>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <Tabs defaultValue="export" className="space-y-4">
          <TabsList>
            <TabsTrigger value="export" className="flex items-center gap-2">
              <Download className="h-4 w-4" />
              Export
            </TabsTrigger>
            <TabsTrigger value="import" className="flex items-center gap-2">
              <Upload className="h-4 w-4" />
              Import / Review
            </TabsTrigger>
            <TabsTrigger value="history" className="flex items-center gap-2">
              <History className="h-4 w-4" />
              History
            </TabsTrigger>
            <TabsTrigger value="settings" className="flex items-center gap-2">
              <Settings className="h-4 w-4" />
              Settings
            </TabsTrigger>
          </TabsList>

          <TabsContent value="export">
            <ExportTab config={config} />
          </TabsContent>

          <TabsContent value="import">
            <ImportTab config={config} />
          </TabsContent>

          <TabsContent value="history">
            <HistoryTab />
          </TabsContent>

          <TabsContent value="settings">
            <SettingsTab config={config} refetch={refetch} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
