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

const CRM_FIELDS = [
  { value: '__skip__', label: '— Skip —' },
  { value: 'first_name', label: 'First Name' },
  { value: 'last_name', label: 'Last Name' },
  { value: 'email', label: 'Email' },
  { value: 'phone', label: 'Phone' },
  { value: 'title', label: 'Title / Position' },
  { value: 'company', label: 'Company' },
  { value: 'city', label: 'City' },
  { value: 'state', label: 'State' },
  { value: 'country', label: 'Country' },
  { value: 'status', label: 'Status' },
  { value: 'source', label: 'Source' },
  { value: 'sarson_rep', label: 'Sarson Rep' },
  { value: 'next_step', label: 'Next Step' },
  { value: 'notes', label: 'Notes' },
  { value: 'website', label: 'Website' },
  { value: 'linkedin_url', label: 'LinkedIn URL' },
  { value: 'department', label: 'Department' },
];

function parseCSV(text: string): { headers: string[]; rows: string[][] } {
  const lines = text.split('\n').filter((l) => l.trim());
  if (lines.length === 0) return { headers: [], rows: [] };
  
  const headers = lines[0].split(',').map((h) => h.trim().replace(/^"|"$/g, ''));
  const rows = lines.slice(1).map((line) =>
    line.split(',').map((cell) => cell.trim().replace(/^"|"$/g, ''))
  );
  return { headers, rows };
}

function autoMapColumns(headers: string[]): Record<number, string> {
  const mapping: Record<number, string> = {};
  const hints: Record<string, string> = {
    first_name: 'first_name', firstname: 'first_name', first: 'first_name',
    last_name: 'last_name', lastname: 'last_name', last: 'last_name',
    email: 'email', email_address: 'email',
    phone: 'phone', telephone: 'phone', mobile: 'phone',
    title: 'title', position: 'title', job_title: 'title',
    company: 'company', organization: 'company', org: 'company', company_name: 'company',
    city: 'city', state: 'state', country: 'country',
    status: 'status', source: 'source',
    notes: 'notes', note: 'notes',
    website: 'website', url: 'website',
    linkedin: 'linkedin_url', linkedin_url: 'linkedin_url',
    rep: 'sarson_rep', sarson_rep: 'sarson_rep', assigned: 'sarson_rep',
    next_step: 'next_step', nextstep: 'next_step',
  };

  headers.forEach((header, idx) => {
    const key = header.toLowerCase().replace(/[\s_-]+/g, '_');
    if (hints[key]) {
      mapping[idx] = hints[key];
    }
  });

  return mapping;
}

export default function ImportPage() {
  useEffect(() => { document.title = 'Import — Sarson Funds CRM'; }, []);
  const [step, setStep] = useState(1);
  const [file, setFile] = useState<File | null>(null);
  const [headers, setHeaders] = useState<string[]>([]);
  const [rows, setRows] = useState<string[][]>([]);
  const [columnMap, setColumnMap] = useState<Record<number, string>>({});
  const [result, setResult] = useState<{
    imported_count: number;
    updated_count: number;
    skipped_count: number;
    error_count: number;
  } | null>(null);
  const [progress, setProgress] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback((f: File) => {
    setFile(f);
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      const parsed = parseCSV(text);
      setHeaders(parsed.headers);
      setRows(parsed.rows);
      setColumnMap(autoMapColumns(parsed.headers));
      setStep(2);
    };
    reader.readAsText(f);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const f = e.dataTransfer.files[0];
      if (f && f.name.endsWith('.csv')) handleFile(f);
    },
    [handleFile]
  );

  const importMutation = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error('No file');

      // Step 1: Upload the CSV
      const formData = new FormData();
      formData.append('file', file);

      setProgress(10);
      const uploadRes = await api.post('/imports/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (p) => {
          if (p.total) setProgress(Math.round((p.loaded / p.total) * 40));
        },
      });

      const importId = uploadRes.data.import_id;
      setProgress(50);

      // Step 2: Build column mapping and execute
      const mapping: Record<string, string> = {};
      Object.entries(columnMap).forEach(([idx, field]) => {
        if (field && field !== '__skip__') {
          mapping[headers[parseInt(idx)]] = field;
        }
      });

      const execRes = await api.post(`/imports/${importId}/execute`, {
        column_mapping: mapping,
      });

      setProgress(100);
      return execRes.data;
    },
    onSuccess: (data) => {
      setResult({
        imported_count: data.created || 0,
        updated_count: data.updated || 0,
        skipped_count: data.skipped || 0,
        error_count: (data.errors || []).length,
      });
      setStep(4);
      toast.success(`Import complete — ${data.created || 0} created, ${data.updated || 0} updated`);
    },
    onError: () => {
      toast.error('Import failed. Please check your file and try again.');
    },
  });

  const mappedCount = Object.values(columnMap).filter((v) => v && v !== '__skip__').length;
  const previewRows = rows.slice(0, 10);

  // Validation summary
  const validationErrors: string[] = [];
  const emailIdx = Object.entries(columnMap).find(([, v]) => v === 'email')?.[0];
  if (!emailIdx && step >= 2) validationErrors.push('No column mapped to Email');

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
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              className="border-2 border-dashed rounded-lg p-12 text-center cursor-pointer hover:bg-muted/30 transition-colors"
              onClick={() => fileRef.current?.click()}
            >
              <p className="text-lg font-medium">Drop CSV file here</p>
              <p className="text-sm text-muted-foreground mt-1">or click to browse</p>
              <input
                ref={fileRef}
                type="file"
                accept=".csv"
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
      {step === 2 && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Map CSV Columns → CRM Fields
                <Badge variant="secondary" className="ml-2">{mappedCount} of {headers.length} mapped</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {headers.map((header, idx) => (
                  <div key={idx} className="flex items-center gap-4">
                    <span className="w-48 text-sm font-mono truncate">{header}</span>
                    <span className="text-muted-foreground">→</span>
                    <Select
                      value={columnMap[idx] || '__skip__'}
                      onValueChange={(v) => setColumnMap({ ...columnMap, [idx]: v })}
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
                    {/* Show sample value */}
                    <span className="text-xs text-muted-foreground truncate max-w-[200px]">
                      e.g. {rows[0]?.[idx] || '—'}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {validationErrors.length > 0 && (
            <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-md text-sm text-yellow-800">
              {validationErrors.map((err, i) => <p key={i}>⚠ {err}</p>)}
            </div>
          )}

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setStep(1)}>← Back</Button>
            <Button onClick={() => setStep(3)}>Preview Data →</Button>
          </div>
        </div>
      )}

      {/* Step 3: Data Preview */}
      {step === 3 && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Preview (first {previewRows.length} of {rows.length} rows)
              </CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    {headers.map((h, i) => {
                      const mapped = columnMap[i];
                      if (!mapped || mapped === '__skip__') return null;
                      return <TableHead key={i}>{CRM_FIELDS.find((f) => f.value === mapped)?.label || mapped}</TableHead>;
                    })}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {previewRows.map((row, ri) => (
                    <TableRow key={ri}>
                      {headers.map((_, ci) => {
                        const mapped = columnMap[ci];
                        if (!mapped || mapped === '__skip__') return null;
                        return <TableCell key={ci} className="text-sm">{row[ci] || '—'}</TableCell>;
                      })}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <div className="text-sm text-muted-foreground">
            <p>Total rows: <strong>{rows.length.toLocaleString()}</strong></p>
            <p>Mapped fields: <strong>{mappedCount}</strong></p>
          </div>

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setStep(2)}>← Back</Button>
            <Button onClick={() => importMutation.mutate()} disabled={importMutation.isPending}>
              {importMutation.isPending ? 'Importing...' : `Import ${rows.length.toLocaleString()} Contacts`}
            </Button>
          </div>

          {importMutation.isPending && (
            <div className="w-full bg-muted rounded-full h-2">
              <div
                className="bg-primary h-2 rounded-full transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
          )}
        </div>
      )}

      {/* Step 4: Results */}
      {step === 4 && result && (
        <Card>
          <CardHeader>
            <CardTitle>Import Complete!</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-4 text-center">
              <div className="p-4 bg-green-50 rounded-lg">
                <p className="text-2xl font-bold text-green-700">{result.imported_count}</p>
                <p className="text-sm text-green-600">Imported</p>
              </div>
              <div className="p-4 bg-blue-50 rounded-lg">
                <p className="text-2xl font-bold text-blue-700">{result.updated_count}</p>
                <p className="text-sm text-blue-600">Updated</p>
              </div>
              <div className="p-4 bg-yellow-50 rounded-lg">
                <p className="text-2xl font-bold text-yellow-700">{result.skipped_count}</p>
                <p className="text-sm text-yellow-600">Skipped</p>
              </div>
              <div className="p-4 bg-red-50 rounded-lg">
                <p className="text-2xl font-bold text-red-700">{result.error_count}</p>
                <p className="text-sm text-red-600">Errors</p>
              </div>
            </div>
            <Button onClick={() => { setStep(1); setFile(null); setResult(null); }}>
              Import More
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
