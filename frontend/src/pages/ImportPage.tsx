import { useState, useCallback, useRef, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
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

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB — Issue #21

const CRM_FIELDS = [
  { value: '__skip__', label: '— Skip —' },
  { value: 'first_name', label: 'First Name' },
  { value: 'middle_name', label: 'Middle Name' },
  { value: 'last_name', label: 'Last Name' },
  { value: 'email', label: 'Email' },
  { value: 'phone', label: 'Phone' },
  { value: 'title', label: 'Title / Position' },
  { value: 'company', label: 'Company' },
  { value: 'city', label: 'City' },
  { value: 'state', label: 'State' },
  { value: 'country', label: 'Country' },
  { value: 'status', label: 'Status' },
  { value: 'lead_source', label: 'Source' },
  { value: 'sarson_rep', label: 'Sarson Rep' },
  { value: 'next_step', label: 'Next Step' },
  { value: 'last_contacted_at', label: 'Last Contacted' },
  { value: 'contacted', label: 'Contacted' },
  { value: 'notes', label: 'Notes' },
  { value: 'website', label: 'Website' },
  { value: 'linkedin_url', label: 'LinkedIn URL' },
  { value: 'profile_url', label: 'Profile URL' },
];

const ACCEPTED_EXTENSIONS = '.csv,.tsv,.xlsx,.xls,.ods,.vcf';

interface UploadResult {
  import_id: string;
  filename: string;
  row_count: number;
  column_preview: string[][];
  header_mapping: Record<string, string>;
}

interface ImportStatus {
  id: string;
  filename: string;
  status: string;
  total_rows: number | null;
  processed_rows: number;
  created: number;
  updated: number;
  skipped: number;
  errors: { row: number; error: string }[];
}

export default function ImportPage() {
  useEffect(() => { document.title = 'Import — Sarson Funds CRM'; }, []);
  const [step, setStep] = useState(1);
  const [file, setFile] = useState<File | null>(null);
  const [uploadData, setUploadData] = useState<UploadResult | null>(null);
  const [columnMap, setColumnMap] = useState<Record<string, string>>({});
  const [result, setResult] = useState<{
    imported_count: number;
    updated_count: number;
    skipped_count: number;
    error_count: number;
  } | null>(null);
  const [progress, setProgress] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const uploadMutation = useMutation({
    mutationFn: async (f: File) => {
      const formData = new FormData();
      formData.append('file', f);
      const res = await api.post('/imports/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return res.data as UploadResult;
    },
    onSuccess: (data) => {
      setUploadData(data);
      const map: Record<string, string> = {};
      Object.entries(data.header_mapping).forEach(([header, field]) => {
        map[header] = field;
      });
      setColumnMap(map);
      setStep(2);
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || 'Upload failed');
    },
  });

  const handleFile = useCallback((f: File) => {
    // Issue #21: Frontend file size check before upload
    if (f.size > MAX_FILE_SIZE) {
      toast.error(`File too large (${(f.size / 1024 / 1024).toFixed(1)}MB). Maximum is 10MB.`);
      return;
    }
    setFile(f);
    uploadMutation.mutate(f);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const f = e.dataTransfer.files[0];
      if (f) handleFile(f);
    },
    [handleFile]
  );

  // Issue #23: Poll for real progress
  const startPolling = useCallback((importId: string) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const res = await api.get<ImportStatus>(`/imports/${importId}`);
        const data = res.data;
        const total = data.total_rows || 1;
        const pct = Math.min(Math.round((data.processed_rows / total) * 100), 99);
        setProgress(pct);

        if (data.status === 'complete' || data.status === 'failed') {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          setProgress(100);
          setResult({
            imported_count: data.created || 0,
            updated_count: data.updated || 0,
            skipped_count: data.skipped || 0,
            error_count: (data.errors || []).length,
          });
          setStep(4);
          if (data.status === 'complete') {
            toast.success(`Import complete — ${data.created || 0} created`);
          } else {
            toast.error('Import failed. Check error details.');
          }
        }
      } catch {
        // Polling error — keep trying
      }
    }, 2000);
  }, []);

  const executeMutation = useMutation({
    mutationFn: async () => {
      if (!uploadData) throw new Error('No upload');
      setProgress(5);
      const res = await api.post(`/imports/${uploadData.import_id}/execute`, {
        column_mapping: columnMap,
      });
      return res.data as ImportStatus;
    },
    onSuccess: (data) => {
      if (data.status === 'complete') {
        setProgress(100);
        setResult({
          imported_count: data.created || 0,
          updated_count: data.updated || 0,
          skipped_count: data.skipped || 0,
          error_count: (data.errors || []).length,
        });
        setStep(4);
        toast.success(`Import complete — ${data.created || 0} created`);
      } else if (data.status === 'processing' && uploadData) {
        // Start polling for progress
        startPolling(uploadData.import_id);
      } else if (data.status === 'failed') {
        setProgress(100);
        setResult({
          imported_count: data.created || 0,
          updated_count: data.updated || 0,
          skipped_count: data.skipped || 0,
          error_count: (data.errors || []).length,
        });
        setStep(4);
        toast.error('Import failed.');
      }
    },
    onError: () => {
      toast.error('Import failed. Please check your file and try again.');
    },
  });

  const allHeaders = uploadData?.column_preview?.[0]
    ? Array.from({ length: uploadData.column_preview[0].length }, (_, i) => {
        const mappingKeys = Object.keys(uploadData.header_mapping);
        return mappingKeys[i] || `Column ${i + 1}`;
      })
    : Object.keys(uploadData?.header_mapping || {});

  const mappedCount = Object.values(columnMap).filter((v) => v && v !== '__skip__' && !v.startsWith('_')).length;
  const previewRows = uploadData?.column_preview?.slice(0, 10) || [];
  const emailMapped = Object.values(columnMap).includes('email');

  const fileTypeLabel = (name: string) => {
    const ext = name.split('.').pop()?.toLowerCase();
    const labels: Record<string, string> = {
      csv: 'CSV', tsv: 'TSV', xlsx: 'Excel', xls: 'Excel',
      ods: 'OpenDocument', vcf: 'vCard',
    };
    return labels[ext || ''] || ext?.toUpperCase() || 'File';
  };

  return (
    <div className="space-y-4 max-w-4xl">
      <h1 className="text-2xl font-bold">Import Contacts</h1>

      {/* Step indicator */}
      <div className="flex gap-2 mb-4">
        {['Upload', 'Map Columns', 'Preview', 'Results'].map((label, i) => (
          <div key={i} className="flex items-center gap-1">
            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
              i + 1 <= step ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'
            }`}>
              {i + 1}
            </div>
            <span className="text-xs text-muted-foreground">{label}</span>
            {i < 3 && <div className="w-8 h-px bg-muted mx-1" />}
          </div>
        ))}
      </div>

      {/* Step 1: Upload */}
      {step === 1 && (
        <Card>
          <CardContent className="py-12">
            <div
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors ${
                isDragging ? 'border-primary bg-primary/5' : 'hover:bg-muted/30'
              }`}
              onClick={() => fileRef.current?.click()}
            >
              <div className="text-4xl mb-3">📁</div>
              <p className="text-lg font-medium">
                {uploadMutation.isPending ? 'Uploading...' : 'Drop file here or click to browse'}
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                Supports CSV, TSV, Excel (.xlsx), OpenDocument (.ods), vCard (.vcf)
              </p>
              <p className="text-xs text-muted-foreground mt-2">Max 10MB · Up to 10,000 rows</p>
              <input
                ref={fileRef}
                type="file"
                accept={ACCEPTED_EXTENSIONS}
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleFile(f);
                }}
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Column Mapping */}
      {step === 2 && uploadData && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                Map Columns → CRM Fields
                <Badge variant="secondary">{fileTypeLabel(uploadData.filename)}</Badge>
                <Badge variant="secondary">{uploadData.row_count.toLocaleString()} rows</Badge>
                <Badge variant="outline">{mappedCount} mapped</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {Object.keys(uploadData.header_mapping).concat(
                  allHeaders.filter(h => !uploadData.header_mapping[h] && !Object.keys(uploadData.header_mapping).includes(h))
                ).filter((h, i, arr) => arr.indexOf(h) === i).map((header, idx) => (
                  <div key={idx} className="flex items-center gap-4">
                    <span className="w-48 text-sm font-mono truncate" title={header}>{header}</span>
                    <span className="text-muted-foreground">→</span>
                    <Select
                      value={columnMap[header] || '__skip__'}
                      onValueChange={(v) => setColumnMap({ ...columnMap, [header]: v })}
                    >
                      <SelectTrigger className="w-48">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {CRM_FIELDS.map((f) => (
                          <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <span className="text-xs text-muted-foreground truncate max-w-[200px]">
                      e.g. {previewRows[0]?.[Object.keys(uploadData.header_mapping).indexOf(header)] || '—'}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {!emailMapped && (
            <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-md text-sm text-yellow-800">
              ⚠ No column mapped to Email — rows without email will be skipped
            </div>
          )}

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => { setStep(1); setFile(null); setUploadData(null); }}>← Back</Button>
            <Button onClick={() => setStep(3)}>Preview Data →</Button>
          </div>
        </div>
      )}

      {/* Step 3: Data Preview */}
      {step === 3 && uploadData && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Preview (first {Math.min(previewRows.length, 5)} of {uploadData.row_count.toLocaleString()} rows)
              </CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    {Object.keys(uploadData.header_mapping).map((h, i) => {
                      const mapped = columnMap[h];
                      if (!mapped || mapped === '__skip__' || mapped.startsWith('_')) return null;
                      return <TableHead key={i}>{CRM_FIELDS.find((f) => f.value === mapped)?.label || mapped}</TableHead>;
                    })}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {previewRows.map((row, ri) => (
                    <TableRow key={ri}>
                      {Object.keys(uploadData.header_mapping).map((h, ci) => {
                        const mapped = columnMap[h];
                        if (!mapped || mapped === '__skip__' || mapped.startsWith('_')) return null;
                        return <TableCell key={ci} className="text-sm">{row[ci] || '—'}</TableCell>;
                      })}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setStep(2)}>← Back</Button>
            <Button onClick={() => executeMutation.mutate()} disabled={executeMutation.isPending}>
              {executeMutation.isPending ? 'Importing...' : `Import ${uploadData.row_count.toLocaleString()} Contacts`}
            </Button>
          </div>

          {(executeMutation.isPending || (progress > 0 && progress < 100)) && (
            <div className="space-y-1">
              <div className="w-full bg-muted rounded-full h-2">
                <div className="bg-primary h-2 rounded-full transition-all" style={{ width: `${progress}%` }} />
              </div>
              <p className="text-xs text-muted-foreground text-center">{progress}%</p>
            </div>
          )}
        </div>
      )}

      {/* Step 4: Results */}
      {step === 4 && result && (
        <Card>
          <CardHeader>
            <CardTitle>Import Complete! ✅</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-4 text-center">
              <div className="p-4 bg-green-50 rounded-lg">
                <p className="text-2xl font-bold text-green-700">{result.imported_count}</p>
                <p className="text-sm text-green-600">Created</p>
              </div>
              <div className="p-4 bg-blue-50 rounded-lg">
                <p className="text-2xl font-bold text-blue-700">{result.updated_count}</p>
                <p className="text-sm text-blue-600">Updated</p>
              </div>
              <div className="p-4 bg-yellow-50 rounded-lg">
                <p className="text-2xl font-bold text-yellow-700">{result.skipped_count}</p>
                <p className="text-sm text-yellow-600">Skipped (dupes/no email)</p>
              </div>
              <div className="p-4 bg-red-50 rounded-lg">
                <p className="text-2xl font-bold text-red-700">{result.error_count}</p>
                <p className="text-sm text-red-600">Errors</p>
              </div>
            </div>
            <Button onClick={() => { setStep(1); setFile(null); setResult(null); setUploadData(null); setProgress(0); }}>
              Import More
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
