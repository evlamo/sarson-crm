import { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, Copy, Check, Loader2, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useAuth } from '@/hooks/useAuth';

interface OpenAPISpec {
  openapi: string;
  info: {
    title: string;
    version: string;
    description?: string;
  };
  paths: Record<string, PathItem>;
}

interface PathItem {
  [method: string]: Operation;
}

interface Operation {
  tags?: string[];
  summary?: string;
  description?: string;
  operationId?: string;
  parameters?: Parameter[];
  requestBody?: RequestBody;
  responses?: Record<string, Response>;
}

interface Parameter {
  name: string;
  in: string;
  required?: boolean;
  description?: string;
  schema?: Schema;
}

interface RequestBody {
  required?: boolean;
  content?: Record<string, { schema?: Schema }>;
}

interface Response {
  description?: string;
}

interface Schema {
  type?: string;
  format?: string;
  $ref?: string;
}

interface GroupedEndpoints {
  [tag: string]: {
    method: string;
    path: string;
    operation: Operation;
  }[];
}

const methodColors: Record<string, string> = {
  get: 'bg-green-100 text-green-800 border-green-200',
  post: 'bg-blue-100 text-blue-800 border-blue-200',
  put: 'bg-amber-100 text-amber-800 border-amber-200',
  patch: 'bg-orange-100 text-orange-800 border-orange-200',
  delete: 'bg-red-100 text-red-800 border-red-200',
};

export default function DocsPage() {
  const isAdmin = useAuth((s) => s.isAdmin);
  const [spec, setSpec] = useState<OpenAPISpec | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedTags, setExpandedTags] = useState<Set<string>>(new Set());
  const [copiedPath, setCopiedPath] = useState<string | null>(null);

  useEffect(() => {
    document.title = 'API Documentation — Sarson Funds CRM';
    if (isAdmin) {
      fetchSpec();
    } else {
      setLoading(false);
    }
  }, [isAdmin]);

  // Admin check - show access denied if not admin
  if (!isAdmin) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-muted-foreground">
        <p className="text-lg font-semibold">Access Denied</p>
        <p className="text-sm mt-1">You don't have permission to view this page.</p>
      </div>
    );
  }

  const fetchSpec = async () => {
    try {
      const res = await fetch('/openapi.json');
      if (!res.ok) throw new Error('Failed to fetch API spec');
      const data = await res.json();
      setSpec(data);
      // Auto-expand first tag
      const tags = getGroupedEndpoints(data);
      const firstTag = Object.keys(tags)[0];
      if (firstTag) setExpandedTags(new Set([firstTag]));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const getGroupedEndpoints = (apiSpec: OpenAPISpec): GroupedEndpoints => {
    const grouped: GroupedEndpoints = {};

    Object.entries(apiSpec.paths).forEach(([path, pathItem]) => {
      Object.entries(pathItem).forEach(([method, operation]) => {
        if (['get', 'post', 'put', 'patch', 'delete'].includes(method)) {
          const tags = operation.tags || ['Untagged'];
          tags.forEach((tag) => {
            if (!grouped[tag]) grouped[tag] = [];
            grouped[tag].push({ method, path, operation });
          });
        }
      });
    });

    // Sort tags alphabetically, but put common ones first
    const priorityTags = ['auth', 'contacts', 'companies', 'lists', 'campaigns'];
    const sortedTags = Object.keys(grouped).sort((a, b) => {
      const aLower = a.toLowerCase();
      const bLower = b.toLowerCase();
      const aIdx = priorityTags.indexOf(aLower);
      const bIdx = priorityTags.indexOf(bLower);
      if (aIdx !== -1 && bIdx !== -1) return aIdx - bIdx;
      if (aIdx !== -1) return -1;
      if (bIdx !== -1) return 1;
      return aLower.localeCompare(bLower);
    });

    const result: GroupedEndpoints = {};
    sortedTags.forEach((tag) => {
      result[tag] = grouped[tag];
    });
    return result;
  };

  const toggleTag = (tag: string) => {
    setExpandedTags((prev) => {
      const next = new Set(prev);
      if (next.has(tag)) {
        next.delete(tag);
      } else {
        next.add(tag);
      }
      return next;
    });
  };

  const copyPath = async (path: string) => {
    const fullUrl = `${window.location.origin}/api/v1${path}`;
    await navigator.clipboard.writeText(fullUrl);
    setCopiedPath(path);
    setTimeout(() => setCopiedPath(null), 2000);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-muted-foreground">
        <p className="text-lg font-semibold">Failed to load API documentation</p>
        <p className="text-sm mt-1">{error}</p>
        <Button variant="outline" className="mt-4" onClick={fetchSpec}>
          Retry
        </Button>
      </div>
    );
  }

  if (!spec) return null;

  const grouped = getGroupedEndpoints(spec);
  const endpointCount = Object.values(grouped).flat().length;

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">{spec.info.title}</h1>
        <p className="text-muted-foreground mt-1">
          v{spec.info.version} · {endpointCount} endpoints
        </p>
        {spec.info.description && (
          <p className="text-sm text-muted-foreground mt-2">
            {spec.info.description}
          </p>
        )}
        <div className="mt-3">
          <a
            href="/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-sm text-[#253a52] hover:underline"
          >
            Open Swagger UI <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </div>

      {/* Endpoint Groups */}
      <div className="space-y-2">
        {Object.entries(grouped).map(([tag, endpoints]) => (
          <div key={tag} className="border rounded-lg overflow-hidden">
            {/* Tag Header */}
            <button
              onClick={() => toggleTag(tag)}
              className="w-full flex items-center justify-between p-3 bg-muted/50 hover:bg-muted transition-colors text-left"
            >
              <div className="flex items-center gap-2">
                {expandedTags.has(tag) ? (
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                )}
                <span className="font-medium text-foreground capitalize">
                  {tag.replace(/_/g, ' ')}
                </span>
              </div>
              <span className="text-xs text-muted-foreground">
                {endpoints.length} endpoint{endpoints.length !== 1 && 's'}
              </span>
            </button>

            {/* Endpoints */}
            {expandedTags.has(tag) && (
              <div className="divide-y">
                {endpoints.map(({ method, path, operation }, idx) => (
                  <div key={idx} className="p-3 hover:bg-muted/30 transition-colors">
                    <div className="flex items-start gap-3">
                      {/* Method Badge */}
                      <span
                        className={cn(
                          'px-2 py-0.5 text-xs font-mono uppercase rounded border shrink-0',
                          methodColors[method] || 'bg-gray-100 text-gray-800'
                        )}
                      >
                        {method}
                      </span>

                      {/* Path and Details */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <code className="text-sm font-mono text-foreground break-all">
                            {path}
                          </code>
                          <button
                            onClick={() => copyPath(path)}
                            className="p-1 hover:bg-muted rounded shrink-0"
                            title="Copy URL"
                          >
                            {copiedPath === path ? (
                              <Check className="h-3 w-3 text-green-600" />
                            ) : (
                              <Copy className="h-3 w-3 text-muted-foreground" />
                            )}
                          </button>
                        </div>
                        {(operation.summary || operation.description) && (
                          <p className="text-sm text-muted-foreground mt-1">
                            {operation.summary || operation.description}
                          </p>
                        )}
                        {/* Parameters summary */}
                        {operation.parameters && operation.parameters.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-1">
                            {operation.parameters
                              .filter((p) => p.in === 'query' || p.in === 'path')
                              .slice(0, 5)
                              .map((p, pIdx) => (
                                <span
                                  key={pIdx}
                                  className={cn(
                                    'px-1.5 py-0.5 text-xs rounded',
                                    p.required
                                      ? 'bg-amber-50 text-amber-700'
                                      : 'bg-gray-100 text-gray-600'
                                  )}
                                >
                                  {p.name}
                                  {p.required && '*'}
                                </span>
                              ))}
                            {operation.parameters.length > 5 && (
                              <span className="text-xs text-muted-foreground">
                                +{operation.parameters.length - 5} more
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
