import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  KeyRound,
  Eye,
  EyeOff,
  CheckCircle2,
  XCircle,
  Loader2,
  Shield,
} from 'lucide-react';

// ── Types ─────────────────────────────────────────────────────────────────

interface ProviderField {
  key: string;
  label: string;
  sensitive: boolean;
  placeholder: string;
  help: string;
  current_value: string;
}

interface Provider {
  provider: string;
  label: string;
  is_configured: boolean;
  last_tested_at: string | null;
  last_test_status: string | null;
  fields: ProviderField[];
}

interface TestResult {
  success: boolean;
  message: string;
  detail?: string | null;
}

// ── Provider Card ─────────────────────────────────────────────────────────

function ProviderCard({ provider }: { provider: Provider }) {
  const queryClient = useQueryClient();
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});
  const [showFields, setShowFields] = useState<Record<string, boolean>>({});
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  // Auto-clear test result after 10 seconds
  useEffect(() => {
    if (!testResult) return;
    const timer = setTimeout(() => setTestResult(null), 10000);
    return () => clearTimeout(timer);
  }, [testResult]);

  const saveMutation = useMutation({
    mutationFn: async (data: Record<string, string | undefined>) => {
      const res = await api.put(`/api-controls/${provider.provider}`, data);
      return res.data;
    },
    onSuccess: () => {
      toast.success(`${provider.label} credentials updated`);
      setFieldValues({});
      queryClient.invalidateQueries({ queryKey: ['api-controls-providers'] });
    },
    onError: () => toast.error('Failed to save credentials'),
  });

  const testMutation = useMutation({
    mutationFn: async () => {
      const res = await api.post(`/api-controls/${provider.provider}/test`);
      return res.data as TestResult;
    },
    onSuccess: (data) => {
      setTestResult(data);
      queryClient.invalidateQueries({ queryKey: ['api-controls-providers'] });
      if (data.success) toast.success(data.message);
      else toast.error(data.message);
    },
    onError: () => {
      setTestResult({ success: false, message: 'Test request failed' });
      toast.error('Test request failed');
    },
  });

  const handleSave = () => {
    // Only send non-empty fields
    const payload: Record<string, string | undefined> = {};
    let hasChanges = false;
    for (const field of provider.fields) {
      const val = fieldValues[field.key];
      if (val !== undefined && val !== '') {
        payload[field.key] = val;
        hasChanges = true;
      }
    }
    if (!hasChanges) {
      toast.info('No changes to save');
      return;
    }
    saveMutation.mutate(payload);
  };

  const statusBadge = () => {
    if (provider.is_configured && provider.last_test_status === 'success') {
      return <Badge className="bg-emerald-600 text-white">Connected</Badge>;
    }
    if (provider.is_configured && provider.last_test_status === 'failed') {
      return <Badge variant="destructive">Connection Failed</Badge>;
    }
    if (provider.is_configured) {
      return <Badge className="bg-amber-500 text-white">Untested</Badge>;
    }
    return <Badge variant="secondary">Not Configured</Badge>;
  };

  const relativeTime = (iso: string | null) => {
    if (!iso) return 'Never tested';
    const d = new Date(iso);
    const diff = Date.now() - d.getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'Just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-[#FFE01B] flex items-center justify-center">
            <KeyRound className="h-5 w-5 text-black" />
          </div>
          <div>
            <CardTitle className="text-lg">{provider.label}</CardTitle>
            <p className="text-xs text-muted-foreground mt-0.5">
              Last tested: {relativeTime(provider.last_tested_at)}
            </p>
          </div>
        </div>
        {statusBadge()}
      </CardHeader>
      <CardContent className="space-y-4">
        {provider.fields.map((field) => (
          <div key={field.key} className="space-y-1.5">
            <div className="flex items-center gap-2">
              <Label htmlFor={`${provider.provider}-${field.key}`} className="text-sm font-medium">
                {field.label}
              </Label>
              {field.current_value ? (
                <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-emerald-600 border-emerald-300">
                  ✓ Set
                </Badge>
              ) : (
                <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-muted-foreground">
                  Not set
                </Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground">{field.help}</p>
            <div className="relative">
              <Input
                id={`${provider.provider}-${field.key}`}
                type={field.sensitive && !showFields[field.key] ? 'password' : 'text'}
                placeholder={field.current_value || field.placeholder}
                value={fieldValues[field.key] || ''}
                onChange={(e) =>
                  setFieldValues((prev) => ({ ...prev, [field.key]: e.target.value }))
                }
                className="pr-10"
              />
              {field.sensitive && (
                <button
                  type="button"
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  onClick={() =>
                    setShowFields((prev) => ({ ...prev, [field.key]: !prev[field.key] }))
                  }
                >
                  {showFields[field.key] ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              )}
            </div>
          </div>
        ))}

        <div className="flex items-center gap-3 pt-2">
          <Button onClick={handleSave} disabled={saveMutation.isPending}>
            {saveMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Save Credentials
          </Button>
          <Button
            variant="outline"
            onClick={() => {
              setTestResult(null);
              testMutation.mutate();
            }}
            disabled={testMutation.isPending}
          >
            {testMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Test Connection
          </Button>
        </div>

        {testResult && (
          <div
            className={`flex items-start gap-2 p-3 rounded-md text-sm ${
              testResult.success
                ? 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200'
                : 'bg-red-50 text-red-800 dark:bg-red-950 dark:text-red-200'
            }`}
          >
            {testResult.success ? (
              <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" />
            ) : (
              <XCircle className="h-4 w-4 mt-0.5 shrink-0" />
            )}
            <div>
              <p className="font-medium">{testResult.message}</p>
              {testResult.detail && (
                <p className="text-xs mt-0.5 opacity-80">{testResult.detail}</p>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function ApiControlsPage() {
  const isAdmin = useAuth((s) => s.isAdmin);

  useEffect(() => {
    document.title = 'API Controls — Sarson Funds CRM';
  }, []);

  const { data: providers, isLoading } = useQuery<Provider[]>({
    queryKey: ['api-controls-providers'],
    queryFn: async () => {
      const res = await api.get('/api-controls/providers');
      return res.data;
    },
    enabled: isAdmin,
  });

  if (!isAdmin) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-muted-foreground">
        <Shield className="h-12 w-12 mb-4" />
        <p className="text-lg font-semibold">Admin Access Required</p>
        <p className="text-sm mt-1">You need admin privileges to manage API integrations.</p>
      </div>
    );
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex items-center gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">API Controls</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage external API integrations
          </p>
        </div>
        <Badge variant="outline" className="ml-2 text-xs">Admin only</Badge>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        providers?.map((p) => <ProviderCard key={p.provider} provider={p} />)
      )}
    </div>
  );
}
