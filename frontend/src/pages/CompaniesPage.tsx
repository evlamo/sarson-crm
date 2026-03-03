import { useState, useEffect, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useSearch } from '@tanstack/react-router';
import api from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
import type { Company, PaginatedResponse } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
} from '@/components/ui/sheet';
import { Search, Plus, ExternalLink, Trash2, Building2 } from 'lucide-react';
import { toast } from 'sonner';
import { EditableField } from '@/components/EditableField';
import { getStatus } from '@/lib/statuses';

interface CompanyContact {
  id: string;
  first_name: string | null;
  last_name: string | null;
  full_name: string;
  email: string | null;
  phone: string | null;
  title: string | null;
  status: string;
}

interface CompanyPOC {
  id: string;
  first_name: string | null;
  last_name: string | null;
  full_name: string;
  email: string | null;
  status: string;
}

export default function CompaniesPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const isRestricted = useAuth((s) => s.isRestricted);
  const searchParams = useSearch({ strict: false }) as { q?: string; openId?: string };
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState(searchParams.q || '');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedCompanyId, setSelectedCompanyId] = useState<string | null>(searchParams.openId || null);

  // If openId changes (e.g. navigated from contact page), open that drawer
  useEffect(() => {
    if (searchParams.openId) {
      setSelectedCompanyId(searchParams.openId);
    }
  }, [searchParams.openId]);

  useEffect(() => {
    document.title = 'Companies — Sarson Funds CRM';
  }, []);

  // Debounce search
  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [search]);

  const { data, isLoading } = useQuery({
    queryKey: ['companies', page, debouncedSearch],
    queryFn: async () => {
      const res = await api.get<PaginatedResponse<Company>>('/companies', {
        params: { page, per_page: 50, search: debouncedSearch || undefined },
      });
      return res.data;
    },
  });

  const companies = data?.data || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / 50);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">Companies</h1>
          <Badge variant="secondary">{total}</Badge>
        </div>
        <Button onClick={() => setShowAddModal(true)} size="sm">
          <Plus className="h-4 w-4 mr-1" /> Add Company
        </Button>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search companies..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* Table */}
      <div className="border rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Company Name</TableHead>
              <TableHead>Industry</TableHead>
              <TableHead>Location</TableHead>
              <TableHead>Contacts</TableHead>
              <TableHead>Website</TableHead>
              <TableHead className="w-[60px]" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 6 }).map((_, j) => (
                    <TableCell key={j}><div className="h-4 bg-muted rounded animate-pulse" /></TableCell>
                  ))}
                </TableRow>
              ))
            ) : companies.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-12 text-muted-foreground">
                  {debouncedSearch ? 'No companies match your search' : 'No companies yet'}
                </TableCell>
              </TableRow>
            ) : (
              companies.map((co) => (
                <TableRow key={co.id} className="cursor-pointer hover:bg-muted/50" onClick={() => setSelectedCompanyId(co.id)}>
                  <TableCell className="font-medium">{co.name}</TableCell>
                  <TableCell className="text-muted-foreground">{co.industry || '—'}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {[co.city, co.state].filter(Boolean).join(', ') || '—'}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="cursor-pointer" onClick={(e) => {
                      e.stopPropagation();
                      navigate({ to: '/contacts', search: { search: co.name } });
                    }}>
                      {co.contact_count}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {co.website ? (
                      <a href={co.website} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}>
                        <ExternalLink className="h-4 w-4 text-muted-foreground hover:text-primary" />
                      </a>
                    ) : '—'}
                  </TableCell>
                  <TableCell>
                    {!isRestricted && <DeleteCompanyButton companyId={co.id} />}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages} ({total} companies)
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next</Button>
          </div>
        </div>
      )}

      {/* Add Company Modal */}
      <AddCompanyModal open={showAddModal} onClose={() => setShowAddModal(false)} />

      {/* Company Detail Drawer */}
      {selectedCompanyId && (
        <CompanyDrawer companyId={selectedCompanyId} onClose={() => setSelectedCompanyId(null)} />
      )}
    </div>
  );
}

function DeleteCompanyButton({ companyId }: { companyId: string }) {
  const queryClient = useQueryClient();
  const deleteMutation = useMutation({
    mutationFn: () => api.delete(`/companies/${companyId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['companies'] });
      toast.success('Company deleted');
    },
    onError: () => toast.error('Failed to delete company'),
  });

  return (
    <Button
      variant="ghost"
      size="icon"
      className="h-8 w-8 text-muted-foreground hover:text-red-500"
      onClick={(e) => {
        e.stopPropagation();
        if (confirm('Delete this company?')) deleteMutation.mutate();
      }}
    >
      <Trash2 className="h-4 w-4" />
    </Button>
  );
}

function AddCompanyModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    name: '', website: '', industry: '', city: '', state: '', country: '', notes: '',
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      const payload: Record<string, string> = {};
      for (const [k, v] of Object.entries(form)) {
        if (v.trim()) payload[k] = v.trim();
      }
      await api.post('/companies', payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['companies'] });
      toast.success('Company created');
      setForm({ name: '', website: '', industry: '', city: '', state: '', country: '', notes: '' });
      onClose();
    },
    onError: (err: { response?: { data?: { detail?: string } } }) => {
      toast.error(err?.response?.data?.detail || 'Failed to create company');
    },
  });

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Company</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!form.name.trim()) return;
            createMutation.mutate();
          }}
          className="space-y-3"
        >
          <div><Label>Name *</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></div>
          <div><Label>Website</Label><Input value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} /></div>
          <div><Label>Industry</Label><Input value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })} /></div>
          <div className="grid grid-cols-3 gap-2">
            <div><Label>City</Label><Input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} /></div>
            <div><Label>State</Label><Input value={form.state} onChange={(e) => setForm({ ...form, state: e.target.value })} /></div>
            <div><Label>Country</Label><Input value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} /></div>
          </div>
          <div><Label>Notes</Label><textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} rows={3} className="w-full px-3 py-2 text-sm border rounded-md bg-background" /></div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={!form.name.trim() || createMutation.isPending}>
              {createMutation.isPending ? 'Creating...' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function CompanyDrawer({ companyId, onClose }: { companyId: string; onClose: () => void }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const isRestricted = useAuth((s) => s.isRestricted);

  const { data: company } = useQuery({
    queryKey: ['company', companyId],
    queryFn: async () => {
      const res = await api.get<Company>(`/companies/${companyId}`);
      return res.data;
    },
  });

  const { data: contactsData } = useQuery({
    queryKey: ['company-contacts', companyId],
    queryFn: async () => {
      const res = await api.get<{ data: CompanyContact[] }>(`/companies/${companyId}/contacts`);
      return res.data;
    },
  });

  const { data: poc } = useQuery({
    queryKey: ['company-poc', companyId],
    queryFn: async () => {
      const res = await api.get<CompanyPOC | null>(`/companies/${companyId}/poc`);
      return res.data;
    },
  });

  const assignPocMutation = useMutation({
    mutationFn: (contactId: string) =>
      api.post(`/companies/${companyId}/poc/${contactId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['company-poc', companyId] });
      queryClient.invalidateQueries({ queryKey: ['company-contacts', companyId] });
      queryClient.invalidateQueries({ queryKey: ['companies'] });
      toast.success('POC assigned');
    },
    onError: (err: { response?: { data?: { detail?: string } } }) => toast.error(err?.response?.data?.detail || 'Failed to assign POC'),
  });

  const removePocMutation = useMutation({
    mutationFn: () => api.delete(`/companies/${companyId}/poc`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['company-poc', companyId] });
      queryClient.invalidateQueries({ queryKey: ['company-contacts', companyId] });
      queryClient.invalidateQueries({ queryKey: ['companies'] });
      toast.success('POC removed');
    },
    onError: () => toast.error('Failed to remove POC'),
  });

  const patchCompany = async (field: string, value: string) => {
    try {
      await api.patch(`/companies/${companyId}`, { [field]: value || null });
      queryClient.invalidateQueries({ queryKey: ['company', companyId] });
      queryClient.invalidateQueries({ queryKey: ['companies'] });
      toast.success('Updated');
    } catch (err: { response?: { data?: { detail?: string } } }) {
      toast.error(err?.response?.data?.detail || 'Failed to update');
      throw err;
    }
  };

  const contacts = contactsData?.data || [];

  return (
    <Sheet open onOpenChange={(v) => !v && onClose()}>
      <SheetContent className="w-full sm:w-[min(1330px,88vw)] overflow-auto p-0">
        {/* Drawer header */}
        <div className="px-8 pt-8 pb-5 border-b bg-muted/30">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-3 text-xl">
              <div className="h-10 w-10 rounded-lg bg-[#253a52]/10 flex items-center justify-center shrink-0">
                <Building2 className="h-5 w-5 text-[#253a52]" />
              </div>
              {company?.name || 'Loading...'}
            </SheetTitle>
          </SheetHeader>
        </div>

        {company && (
          <div className="space-y-8 px-8 py-6">
            {/* Editable fields */}
            <div className="space-y-4 text-sm">
              <FieldRow label="Name">
                <EditableField value={company.name} onSave={(v) => patchCompany('name', v)} />
              </FieldRow>
              <FieldRow label="Website">
                <EditableField value={company.website} type="url" onSave={(v) => patchCompany('website', v)} linkHref={company.website || undefined} placeholder="Add website..." />
              </FieldRow>
              <FieldRow label="Industry">
                <EditableField value={company.industry} onSave={(v) => patchCompany('industry', v)} placeholder="Add industry..." />
              </FieldRow>
              <FieldRow label="City">
                <EditableField value={company.city} onSave={(v) => patchCompany('city', v)} placeholder="Add city..." />
              </FieldRow>
              <FieldRow label="State">
                <EditableField value={company.state} onSave={(v) => patchCompany('state', v)} placeholder="Add state..." />
              </FieldRow>
              <FieldRow label="Notes">
                <EditableField value={company.notes} type="textarea" onSave={(v) => patchCompany('notes', v)} placeholder="Add notes..." />
              </FieldRow>
            </div>

            {/* POC */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-widest">Point of Contact</h3>
                {poc && (
                  <button
                    type="button"
                    onClick={() => removePocMutation.mutate()}
                    disabled={removePocMutation.isPending}
                    className="text-xs text-muted-foreground hover:text-destructive transition-colors"
                  >
                    Remove POC
                  </button>
                )}
              </div>
              {poc ? (
                <div className="flex items-center gap-3 p-3 border rounded-lg bg-[#253a52]/5 border-[#253a52]/20">
                  <div className="h-9 w-9 rounded-full bg-[#253a52] text-white flex items-center justify-center text-xs font-bold shrink-0">
                    {(poc.first_name?.[0] || '').toUpperCase()}{(poc.last_name?.[0] || '').toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold">{poc.full_name}</p>
                    {poc.email && <p className="text-xs text-muted-foreground truncate">{poc.email}</p>}
                  </div>
                  <Badge className="bg-[#253a52] text-white text-xs shrink-0">POC</Badge>
                  <button
                    type="button"
                    onClick={() => { onClose(); navigate({ to: '/contacts/$contactId', params: { contactId: poc.id } }); }}
                    className="text-xs text-[#253a52] hover:underline shrink-0"
                  >
                    View →
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2 p-3 border border-dashed rounded-lg text-muted-foreground">
                  <span className="text-sm italic">No POC assigned — click "Make POC" on any contact below.</span>
                </div>
              )}
            </div>

            {/* Contacts */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-widest">Contacts ({contacts.length})</h3>
                <Button variant="ghost" size="sm" className="text-xs" onClick={() => {
                  onClose();
                  navigate({ to: '/contacts', search: { search: company.name } });
                }}>View all</Button>
              </div>
              <div className="space-y-1">
                {contacts.slice(0, 20).map((c) => {
                  const isPoc = poc?.id === c.id;
                  return (
                    <div
                      key={c.id}
                      className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-muted/50 transition-colors group"
                    >
                      <div
                        className="h-8 w-8 rounded-full bg-[#253a52]/10 text-[#253a52] flex items-center justify-center text-xs font-semibold shrink-0 cursor-pointer"
                        onClick={() => { onClose(); navigate({ to: '/contacts/$contactId', params: { contactId: c.id } }); }}
                      >
                        {(c.first_name?.[0] || '').toUpperCase()}{(c.last_name?.[0] || '').toUpperCase()}
                      </div>
                      <div
                        className="flex-1 min-w-0 cursor-pointer"
                        onClick={() => { onClose(); navigate({ to: '/contacts/$contactId', params: { contactId: c.id } }); }}
                      >
                        <span className="text-sm font-medium truncate block">{c.full_name}</span>
                        {c.email && <span className="text-xs text-muted-foreground truncate block">{c.email}</span>}
                      </div>
                      {isPoc ? (
                        <Badge className="bg-[#253a52] text-white text-[10px] shrink-0">POC</Badge>
                      ) : (
                        <>
                          <span className={`inline-flex items-center text-[10px] font-medium px-2 py-0.5 rounded-full border shrink-0 ${getStatus(c.status).badge}`}>
                            {getStatus(c.status).label}
                          </span>
                          <button
                            type="button"
                            onClick={() => assignPocMutation.mutate(c.id)}
                            disabled={assignPocMutation.isPending}
                            className="opacity-0 group-hover:opacity-100 text-[10px] font-medium text-[#253a52] border border-[#253a52]/40 rounded px-1.5 py-0.5 hover:bg-[#253a52] hover:text-white transition-all shrink-0 disabled:opacity-40"
                          >
                            Make POC
                          </button>
                        </>
                      )}
                    </div>
                  );
                })}
                {contacts.length === 0 && (
                  <p className="text-sm text-muted-foreground italic py-2">No contacts at this company</p>
                )}
              </div>
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

function FieldRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-0.5 py-1">
      <span className="text-xs font-medium text-muted-foreground block">{label}</span>
      <div className="text-sm">{children}</div>
    </div>
  );
}
