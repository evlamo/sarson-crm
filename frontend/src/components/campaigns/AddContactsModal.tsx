import { useState, useEffect, useMemo, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '@/lib/api';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Search, ChevronDown, X, Loader2, AlertCircle, Users, Check } from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────────────

interface ContactTag {
  id: string;
  name: string;
}

interface AvailableContact {
  id: string;
  full_name: string;
  email: string | null;
  company: string | null;
  tags: ContactTag[];
  already_in_campaign: boolean;
}

interface ExclusionCounts {
  dnc: number;
  already_in_campaign: number;
  completed_or_rejected: number;
  total: number;
}

interface AvailableContactsResponse {
  data: {
    contacts: AvailableContact[];
    total: number;
    page: number;
    per_page: number;
    excluded_counts: ExclusionCounts;
  };
}

interface Tag {
  id: string;
  name: string;
  contact_count?: number;
}

interface StaticList {
  id: string;
  name: string;
  member_count?: number;
}

interface AddContactsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAddContacts: (contactIds: string[]) => void;
  campaignId: string;
  campaignName?: string;
}

// ── Multi-Select Dropdown Component ────────────────────────────────────────

function MultiSelectDropdown({
  label,
  options,
  selectedIds,
  onSelectionChange,
  placeholder,
  disabled,
}: {
  label: string;
  options: { id: string; name: string; count?: number }[];
  selectedIds: string[];
  onSelectionChange: (ids: string[]) => void;
  placeholder: string;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);

  const selectedNames = useMemo(() => {
    return options
      .filter((o) => selectedIds.includes(o.id))
      .map((o) => o.name);
  }, [options, selectedIds]);

  const toggleOption = (id: string) => {
    if (selectedIds.includes(id)) {
      onSelectionChange(selectedIds.filter((i) => i !== id));
    } else {
      onSelectionChange([...selectedIds, id]);
    }
  };

  const clearAll = (e: React.MouseEvent) => {
    e.stopPropagation();
    onSelectionChange([]);
  };

  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium text-gray-700">{label}</label>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={open}
            disabled={disabled || options.length === 0}
            className="w-full justify-between h-10 font-normal"
          >
            <span className="truncate">
              {selectedNames.length === 0
                ? placeholder
                : selectedNames.length === 1
                ? selectedNames[0]
                : `${selectedNames.length} selected`}
            </span>
            <div className="flex items-center gap-1">
              {selectedIds.length > 0 && (
                <X
                  className="h-4 w-4 text-gray-400 hover:text-gray-600"
                  onClick={clearAll}
                />
              )}
              <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
            </div>
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[300px] p-0" align="start">
          <Command>
            <CommandInput placeholder={`Search ${label.toLowerCase()}...`} />
            <CommandList>
              <CommandEmpty>No {label.toLowerCase()} found.</CommandEmpty>
              <CommandGroup>
                {options.map((option) => (
                  <CommandItem
                    key={option.id}
                    value={option.name}
                    onSelect={() => toggleOption(option.id)}
                    className="cursor-pointer"
                  >
                    <div className="flex items-center gap-2 w-full">
                      <div
                        className={`h-4 w-4 border rounded flex items-center justify-center ${
                          selectedIds.includes(option.id)
                            ? 'bg-[#253a52] border-[#253a52]'
                            : 'border-gray-300'
                        }`}
                      >
                        {selectedIds.includes(option.id) && (
                          <Check className="h-3 w-3 text-white" />
                        )}
                      </div>
                      <span className="flex-1 truncate">{option.name}</span>
                      {option.count !== undefined && (
                        <span className="text-xs text-gray-400">({option.count})</span>
                      )}
                    </div>
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────

export function AddContactsModal({
  isOpen,
  onClose,
  onAddContacts,
  campaignId,
  campaignName,
}: AddContactsModalProps) {
  const queryClient = useQueryClient();

  // State
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [selectedLists, setSelectedLists] = useState<string[]>([]);
  const [selectedContacts, setSelectedContacts] = useState<Set<string>>(new Set());
  const [page, setPage] = useState(1);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setPage(1); // Reset to page 1 on search change
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Reset on close
  useEffect(() => {
    if (!isOpen) {
      setSearchQuery('');
      setDebouncedSearch('');
      setSelectedTags([]);
      setSelectedLists([]);
      setSelectedContacts(new Set());
      setPage(1);
    }
  }, [isOpen]);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [selectedTags, selectedLists]);

  // ── Queries ──

  // Fetch tags
  const { data: tagsData } = useQuery<{ data: Tag[] }>({
    queryKey: ['tags'],
    queryFn: async () => {
      const res = await api.get('/api/v1/tags');
      return res.data;
    },
    enabled: isOpen,
  });

  // Fetch lists
  const { data: listsData } = useQuery<{ data: StaticList[] }>({
    queryKey: ['lists'],
    queryFn: async () => {
      const res = await api.get('/api/v1/lists');
      return res.data;
    },
    enabled: isOpen,
  });

  // Fetch available contacts
  const {
    data: contactsData,
    isLoading,
    isFetching,
    error,
  } = useQuery<AvailableContactsResponse>({
    queryKey: [
      'available-contacts',
      campaignId,
      debouncedSearch,
      selectedTags,
      selectedLists,
      page,
    ],
    queryFn: async () => {
      const params: Record<string, string> = {
        page: String(page),
        per_page: '50',
      };
      if (debouncedSearch) params.search = debouncedSearch;
      if (selectedTags.length > 0) params.tag_ids = selectedTags.join(',');
      if (selectedLists.length > 0) params.list_ids = selectedLists.join(',');

      const res = await api.get(`/api/v1/sales-campaigns/${campaignId}/available-contacts`, {
        params,
      });
      return res.data;
    },
    enabled: isOpen && !!campaignId,
  });

  // ── Mutations ──

  const addContactsMutation = useMutation({
    mutationFn: async (contactIds: string[]) => {
      const res = await api.post(`/api/v1/sales-campaigns/${campaignId}/contacts/bulk`, {
        contact_ids: contactIds,
        initial_status: 'active',
      });
      return res.data;
    },
    onSuccess: (result) => {
      const messages: string[] = [];
      if (result.added > 0) {
        messages.push(`${result.added} contact${result.added !== 1 ? 's' : ''} added`);
      }
      if (result.skipped_dnc > 0) {
        messages.push(`${result.skipped_dnc} DNC skipped`);
      }
      if (result.skipped_existing > 0) {
        messages.push(`${result.skipped_existing} already in campaign`);
      }
      toast.success(messages.join(', ') || 'Contacts processed');
      queryClient.invalidateQueries({ queryKey: ['sales-campaign-contacts', campaignId] });
      queryClient.invalidateQueries({ queryKey: ['sales-campaigns'] });
      onClose();
    },
    onError: () => {
      toast.error('Failed to add contacts');
    },
  });

  // ── Handlers ──

  const toggleContactSelection = useCallback((contactId: string) => {
    setSelectedContacts((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(contactId)) {
        newSet.delete(contactId);
      } else {
        newSet.add(contactId);
      }
      return newSet;
    });
  }, []);

  const toggleSelectAll = useCallback(() => {
    const contacts = contactsData?.data?.contacts || [];
    const availableContacts = contacts.filter((c) => !c.already_in_campaign);
    
    if (availableContacts.every((c) => selectedContacts.has(c.id))) {
      // Deselect all on current page
      setSelectedContacts((prev) => {
        const newSet = new Set(prev);
        availableContacts.forEach((c) => newSet.delete(c.id));
        return newSet;
      });
    } else {
      // Select all on current page
      setSelectedContacts((prev) => {
        const newSet = new Set(prev);
        availableContacts.forEach((c) => newSet.add(c.id));
        return newSet;
      });
    }
  }, [contactsData, selectedContacts]);

  const handleAddContacts = () => {
    const ids = Array.from(selectedContacts);
    if (ids.length === 0) return;
    addContactsMutation.mutate(ids);
  };

  // ── Computed values ──

  const tags = tagsData?.data || [];
  const lists = listsData?.data || [];
  const contacts = contactsData?.data?.contacts || [];
  const total = contactsData?.data?.total || 0;
  const excludedCounts = contactsData?.data?.excluded_counts || {
    dnc: 0,
    already_in_campaign: 0,
    completed_or_rejected: 0,
    total: 0,
  };
  const totalPages = Math.ceil(total / 50);
  const availableOnPage = contacts.filter((c) => !c.already_in_campaign);
  const allPageSelected = availableOnPage.length > 0 && availableOnPage.every((c) => selectedContacts.has(c.id));

  const tagOptions = tags.map((t) => ({
    id: t.id,
    name: t.name,
    count: t.contact_count,
  }));

  const listOptions = lists.map((l) => ({
    id: l.id,
    name: l.name,
    count: l.member_count,
  }));

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-[90vw] w-[90vw] h-[85vh] max-h-[85vh] flex flex-col p-0">
        {/* Header */}
        <DialogHeader className="px-6 py-4 border-b shrink-0">
          <DialogTitle className="text-xl">
            Add Contacts to Campaign{campaignName ? `: ${campaignName}` : ''}
          </DialogTitle>
        </DialogHeader>

        {/* Filters Section */}
        <div className="px-6 py-4 border-b bg-gray-50/50 shrink-0">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Search */}
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-gray-700">Search</label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  type="text"
                  placeholder="Search name, email, company..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>

            {/* Tags Dropdown */}
            <MultiSelectDropdown
              label="Tags"
              options={tagOptions}
              selectedIds={selectedTags}
              onSelectionChange={setSelectedTags}
              placeholder="All Tags"
            />

            {/* Lists Dropdown */}
            <MultiSelectDropdown
              label="Lists"
              options={listOptions}
              selectedIds={selectedLists}
              onSelectionChange={setSelectedLists}
              placeholder="All Lists"
            />
          </div>

          {/* Exclusion Info */}
          {excludedCounts.total > 0 && (
            <div className="mt-3 flex items-center gap-2 text-sm text-amber-700 bg-amber-50 px-3 py-2 rounded-md">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>
                {excludedCounts.total.toLocaleString()} contacts excluded
                {' ('}
                {excludedCounts.dnc > 0 && `${excludedCounts.dnc.toLocaleString()} DNC`}
                {excludedCounts.dnc > 0 && excludedCounts.completed_or_rejected > 0 && ', '}
                {excludedCounts.completed_or_rejected > 0 &&
                  `${excludedCounts.completed_or_rejected.toLocaleString()} completed/rejected`}
                {')'}
              </span>
            </div>
          )}
        </div>

        {/* Contacts Table */}
        <div className="flex-1 overflow-hidden flex flex-col px-6 py-4">
          {/* Selection Header */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                size="sm"
                onClick={toggleSelectAll}
                disabled={availableOnPage.length === 0}
              >
                {allPageSelected ? 'Deselect All' : `Select All (${availableOnPage.length})`}
              </Button>
              <span className="text-sm text-gray-600">
                <strong>{selectedContacts.size}</strong> selected
              </span>
            </div>
            <span className="text-sm text-gray-500">
              Showing {contacts.length} of {total.toLocaleString()} available contacts
            </span>
          </div>

          {/* Table Container */}
          <div className="flex-1 overflow-auto border rounded-lg bg-white">
            {isLoading ? (
              <div className="flex flex-col items-center justify-center h-full gap-3">
                <Loader2 className="h-8 w-8 animate-spin text-[#253a52]" />
                <span className="text-sm text-gray-500">Loading contacts...</span>
              </div>
            ) : error ? (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-red-600">
                <AlertCircle className="h-8 w-8" />
                <span className="text-sm">Failed to load contacts</span>
              </div>
            ) : contacts.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-gray-500">
                <Users className="h-12 w-12 opacity-30" />
                <span className="text-sm">No contacts found</span>
                {(debouncedSearch || selectedTags.length > 0 || selectedLists.length > 0) && (
                  <span className="text-xs">Try adjusting your filters</span>
                )}
              </div>
            ) : (
              <Table>
                <TableHeader className="sticky top-0 bg-gray-50">
                  <TableRow>
                    <TableHead className="w-12"></TableHead>
                    <TableHead className="min-w-[200px]">Name</TableHead>
                    <TableHead className="min-w-[250px]">Email</TableHead>
                    <TableHead className="min-w-[180px]">Company</TableHead>
                    <TableHead className="min-w-[200px]">Tags</TableHead>
                    <TableHead className="w-20">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {contacts.map((contact) => (
                    <TableRow
                      key={contact.id}
                      className={
                        contact.already_in_campaign
                          ? 'opacity-50 bg-gray-50'
                          : selectedContacts.has(contact.id)
                          ? 'bg-blue-50/50'
                          : 'hover:bg-gray-50'
                      }
                    >
                      <TableCell>
                        <Checkbox
                          checked={selectedContacts.has(contact.id)}
                          onCheckedChange={() => toggleContactSelection(contact.id)}
                          disabled={contact.already_in_campaign}
                          aria-label={`Select ${contact.full_name}`}
                        />
                      </TableCell>
                      <TableCell className="font-medium">{contact.full_name}</TableCell>
                      <TableCell className="text-gray-600">{contact.email || '—'}</TableCell>
                      <TableCell className="text-gray-600">{contact.company || '—'}</TableCell>
                      <TableCell>
                        {contact.tags.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {contact.tags.slice(0, 3).map((tag) => (
                              <Badge
                                key={tag.id}
                                variant="secondary"
                                className="text-xs bg-blue-100 text-blue-800 hover:bg-blue-100"
                              >
                                {tag.name}
                              </Badge>
                            ))}
                            {contact.tags.length > 3 && (
                              <Badge variant="secondary" className="text-xs">
                                +{contact.tags.length - 3}
                              </Badge>
                            )}
                          </div>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {contact.already_in_campaign && (
                          <Badge variant="outline" className="text-xs bg-green-50 text-green-700 border-green-200">
                            Added
                          </Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-3 pt-3 border-t">
              <span className="text-sm text-gray-600">
                Page {page} of {totalPages}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1 || isFetching}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages || isFetching}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <DialogFooter className="px-6 py-4 border-t shrink-0 bg-gray-50/50">
          <div className="flex items-center justify-between w-full">
            <span className="text-sm text-gray-500">
              {selectedContacts.size > 0 && (
                <>
                  <strong>{selectedContacts.size}</strong> contact{selectedContacts.size !== 1 ? 's' : ''} will be added
                </>
              )}
            </span>
            <div className="flex gap-3">
              <Button variant="outline" onClick={onClose} disabled={addContactsMutation.isPending}>
                Cancel
              </Button>
              <Button
                onClick={handleAddContacts}
                disabled={selectedContacts.size === 0 || addContactsMutation.isPending}
                className="bg-[#253a52] hover:bg-[#253a52]/90 min-w-[200px]"
              >
                {addContactsMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Adding...
                  </>
                ) : (
                  `Add Selected Contacts (${selectedContacts.size})`
                )}
              </Button>
            </div>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
