import { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from '@tanstack/react-router';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
  type RowSelectionState,
} from '@tanstack/react-table';
import api from '@/lib/api';
import type { Contact, PaginatedResponse } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
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
import { Search } from 'lucide-react';

// Inline editable Last Contact cell — date picker
function InlineLastContact({ contact }: { contact: Contact }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const mutation = useMutation({
    mutationFn: async (value: string) => {
      await api.patch(`/contacts/${contact.id}`, { last_contacted_at: value || null });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
      queryClient.invalidateQueries({ queryKey: ['contact', contact.id] });
      setEditing(false);
    },
  });

  const start = (e: React.MouseEvent) => {
    e.stopPropagation();
    const iso = contact.last_contacted_at ? contact.last_contacted_at.slice(0, 10) : '';
    setDraft(iso);
    setEditing(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const save = () => {
    const current = contact.last_contacted_at ? contact.last_contacted_at.slice(0, 10) : '';
    if (draft !== current) mutation.mutate(draft);
    else setEditing(false);
  };

  if (editing) {
    return (
      <input
        ref={inputRef}
        type="date"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={save}
        onKeyDown={(e) => {
          if (e.key === 'Enter') { e.preventDefault(); save(); }
          if (e.key === 'Escape') setEditing(false);
          e.stopPropagation();
        }}
        onClick={(e) => e.stopPropagation()}
        className="w-full h-7 px-2 text-sm border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-primary"
      />
    );
  }

  const display = contact.last_contacted_at
    ? new Date(contact.last_contacted_at).toLocaleDateString()
    : null;

  return (
    <span
      onClick={start}
      className={`block w-full truncate text-sm cursor-pointer rounded px-1 -mx-1 hover:bg-muted transition-colors ${
        display ? '' : 'text-muted-foreground italic'
      }`}
      title={display || 'Click to set date...'}
    >
      {display || '—'}
    </span>
  );
}

// Inline editable Next Step cell
function InlineNextStep({ contact }: { contact: Contact }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const mutation = useMutation({
    mutationFn: async (value: string) => {
      await api.patch(`/contacts/${contact.id}`, { next_step: value || null });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
      queryClient.invalidateQueries({ queryKey: ['contact', contact.id] });
      setEditing(false);
    },
  });

  const start = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDraft(contact.next_step || '');
    setEditing(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const save = () => {
    if (draft !== (contact.next_step || '')) {
      mutation.mutate(draft);
    } else {
      setEditing(false);
    }
  };

  if (editing) {
    return (
      <input
        ref={inputRef}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={save}
        onKeyDown={(e) => {
          if (e.key === 'Enter') { e.preventDefault(); save(); }
          if (e.key === 'Escape') setEditing(false);
          e.stopPropagation();
        }}
        onClick={(e) => e.stopPropagation()}
        className="w-full h-7 px-2 text-sm border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-primary"
        placeholder="Add next step..."
      />
    );
  }

  return (
    <span
      onClick={start}
      className={`block w-full truncate text-sm cursor-pointer rounded px-1 -mx-1 hover:bg-muted transition-colors ${
        contact.next_step ? '' : 'text-muted-foreground italic'
      }`}
      title={contact.next_step || 'Click to add...'}
    >
      {contact.next_step || '—'}
    </span>
  );
}

// Inline editable Sales Rep cell — single field, compact
function InlineSalesRep({ contact }: { contact: Contact }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const mutation = useMutation({
    mutationFn: async (value: string) => {
      await api.patch(`/contacts/${contact.id}`, { sarson_rep: value || null });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] });
      queryClient.invalidateQueries({ queryKey: ['contact', contact.id] });
      setEditing(false);
    },
  });

  const start = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDraft(contact.sarson_rep || '');
    setEditing(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const save = () => {
    if (draft !== (contact.sarson_rep || '')) mutation.mutate(draft);
    else setEditing(false);
  };

  if (editing) {
    return (
      <input
        ref={inputRef}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={save}
        onKeyDown={(e) => {
          if (e.key === 'Enter') { e.preventDefault(); save(); }
          if (e.key === 'Escape') setEditing(false);
          e.stopPropagation();
        }}
        onClick={(e) => e.stopPropagation()}
        placeholder="Assign rep..."
        className="w-full h-7 px-2 text-sm border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-primary"
      />
    );
  }

  return (
    <span
      onClick={start}
      className={`block w-full truncate text-sm cursor-pointer rounded px-1 -mx-1 hover:bg-muted transition-colors ${
        contact.sarson_rep ? '' : 'text-muted-foreground italic'
      }`}
      title={contact.sarson_rep || 'Click to assign...'}
    >
      {contact.sarson_rep || '—'}
    </span>
  );
}

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-100 text-green-800',
  inactive: 'bg-gray-100 text-gray-800',
  do_not_contact: 'bg-red-100 text-red-800',
  unsubscribed: 'bg-yellow-100 text-yellow-800',
  hot: 'bg-orange-100 text-orange-800',
  cold: 'bg-blue-100 text-blue-800',
  prospect: 'bg-purple-100 text-purple-800',
  lead: 'bg-indigo-100 text-indigo-800',
  customer: 'bg-emerald-100 text-emerald-800',
};

export default function ContactsPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [limit] = useState(50);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [sorting, setSorting] = useState<SortingState>([]);
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [salesRepFilter, setSalesRepFilter] = useState<string>('');

  // Debounced search — 300ms
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  // Set page title
  useEffect(() => { document.title = 'Contacts — Sarson Funds CRM'; }, []);

  // Map frontend column ids to backend sortable fields
  const SORT_FIELD_MAP: Record<string, string> = {
    full_name: 'last_name',
    first_name: 'first_name',
    last_name: 'last_name',
    company_name: 'company',
    last_contacted_at: 'last_contacted_at',
    follow_up_date: 'follow_up_date',
    title: 'title',
    email: 'email',
    phone: 'phone',
    next_step: 'next_step',
    contacted: 'contacted',
    status: 'status',
  };
  const rawSortField = sorting[0]?.id || 'last_name'; // default sort: last name A→Z
  const sortField = SORT_FIELD_MAP[rawSortField] || rawSortField;
  const sortOrder = sorting[0]?.desc ? 'desc' : 'asc';

  const { data, isLoading } = useQuery({
    queryKey: ['contacts', page, limit, search, sortField, sortOrder, statusFilter, salesRepFilter],
    queryFn: async () => {
      const params: Record<string, string> = {
        page: String(page),
        per_page: String(limit),
        sort: sortField,
        order: sortOrder,
      };
      if (search) params.search = search;
      if (statusFilter !== 'all') params.status = statusFilter;
      if (salesRepFilter.trim()) params.sarson_rep = salesRepFilter.trim();

      const res = await api.get<PaginatedResponse<Contact>>('/contacts', { params });
      return res.data;
    },
  });

  const columns = useMemo<ColumnDef<Contact>[]>(
    () => [
      {
        id: 'select',
        header: ({ table }) => (
          <Checkbox
            checked={table.getIsAllPageRowsSelected()}
            onCheckedChange={(v) => table.toggleAllPageRowsSelected(!!v)}
          />
        ),
        cell: ({ row }) => (
          <Checkbox
            checked={row.getIsSelected()}
            onCheckedChange={(v) => row.toggleSelected(!!v)}
          />
        ),
        enableSorting: false,
        size: 40,
      },
      {
        accessorKey: 'first_name',
        header: 'First Name',
        size: 130,
        cell: ({ row }) => (
          <span className="font-medium">{row.original.first_name || '—'}</span>
        ),
      },
      {
        accessorKey: 'last_name',
        header: 'Last Name',
        size: 130,
        cell: ({ row }) => (
          <span className="font-medium">{row.original.last_name || '—'}</span>
        ),
      },
      { accessorKey: 'company_name', header: 'Company', size: 150, cell: ({ getValue }) => getValue<string | null>() || '—' },
      { accessorKey: 'title', header: 'Position', size: 140 },
      { accessorKey: 'email', header: 'Email', size: 200 },
      { accessorKey: 'phone', header: 'Phone', size: 120 },
      {
        accessorKey: 'last_contacted_at',
        header: 'Last Contact',
        size: 130,
        cell: ({ row }) => <InlineLastContact contact={row.original} />,
      },
      {
        accessorKey: 'next_step',
        header: 'Next Step',
        size: 200,
        cell: ({ row }) => <InlineNextStep contact={row.original} />,
      },

      {
        accessorKey: 'sarson_rep',
        header: 'Sales Rep',
        size: 160,
        cell: ({ row }) => <InlineSalesRep contact={row.original} />,
      },
      {
        accessorKey: 'status',
        header: 'Status',
        size: 100,
        cell: ({ getValue }) => {
          const s = getValue<string>();
          return (
            <Badge variant="secondary" className={STATUS_COLORS[s] || 'bg-gray-100 text-gray-800'}>
              {s}
            </Badge>
          );
        },
      },
    ],
    []
  );

  const table = useReactTable({
    data: data?.data || [],
    columns,
    state: { sorting, rowSelection },
    onSortingChange: setSorting,
    onRowSelectionChange: setRowSelection,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    manualPagination: true,
    pageCount: data ? Math.ceil(data.total / (data.per_page || limit)) : 0,
    enableRowSelection: true,
  });

  const selectedCount = Object.keys(rowSelection).length;
  const totalPages = data ? Math.ceil(data.total / limit) : 0;
  const total = data?.total || 0;
  const startItem = total > 0 ? (page - 1) * limit + 1 : 0;
  const endItem = Math.min(page * limit, total);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Contacts</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {total > 0 ? `Showing ${startItem}–${endItem} of ${total.toLocaleString()} contacts` : 'No contacts'}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search contacts..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="w-72 pl-9"
          />
        </div>

        <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="inactive">Inactive</SelectItem>
            <SelectItem value="hot">Hot</SelectItem>
            <SelectItem value="cold">Cold</SelectItem>
            <SelectItem value="prospect">Prospect</SelectItem>
            <SelectItem value="do_not_contact">Do Not Contact</SelectItem>
            <SelectItem value="unsubscribed">Unsubscribed</SelectItem>
          </SelectContent>
        </Select>

        <div className="relative">
          <Search className="absolute left-2.5 top-2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={salesRepFilter}
            onChange={(e) => { setSalesRepFilter(e.target.value); setPage(1); }}
            placeholder="Filter by rep..."
            className="pl-8 pr-3 h-9 w-40 text-sm border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
      </div>

      {/* Bulk actions bar */}
      {selectedCount > 0 && (
        <div className="flex items-center gap-3 p-3 bg-muted rounded-lg">
          <span className="text-sm font-medium">{selectedCount} selected</span>
          <Button variant="outline" size="sm">Add Tag</Button>
          <Button variant="outline" size="sm">Assign</Button>
          <Button variant="outline" size="sm">Export</Button>
          <Button variant="destructive" size="sm">Delete</Button>
        </div>
      )}

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((hg) => (
              <TableRow key={hg.id}>
                {hg.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    className={cn(
                      header.column.getCanSort() ? 'cursor-pointer select-none' : '',
                      'whitespace-nowrap'
                    )}
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    <span className="inline-flex items-center gap-1">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {header.column.getIsSorted() === 'asc' && <span className="text-primary">↑</span>}
                      {header.column.getIsSorted() === 'desc' && <span className="text-primary">↓</span>}
                    </span>
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 8 }).map((_, i) => (
                <TableRow key={i}>
                  {columns.map((_, j) => (
                    <TableCell key={j}>
                      <div className="h-4 bg-muted rounded animate-pulse" style={{ width: `${50 + Math.random() * 50}%` }} />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : !table.getRowModel().rows.length ? (
              <TableRow>
                <TableCell colSpan={columns.length} className="text-center py-12">
                  <div className="text-muted-foreground">
                    <p className="text-base font-medium">
                      {search ? 'No contacts match your search' : 'No contacts found'}
                    </p>
                    <p className="text-sm mt-1">
                      {search ? 'Try adjusting your search or filters' : 'Import contacts to get started'}
                    </p>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  className="cursor-pointer hover:bg-muted/50 transition-colors"
                  onClick={() => navigate({ to: '/contacts/$contactId', params: { contactId: row.original.id } })}
                  data-state={row.getIsSelected() ? 'selected' : undefined}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id} onClick={cell.column.id === 'select' ? (e: React.MouseEvent) => e.stopPropagation() : undefined}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          {total > 0 ? `Page ${page} of ${totalPages}` : ''}
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}

function cn(...classes: (string | boolean | undefined)[]) {
  return classes.filter(Boolean).join(' ');
}
