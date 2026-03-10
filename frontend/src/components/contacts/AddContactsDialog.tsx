import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import api from '@/lib/api';

interface Contact {
  id: string;
  full_name: string;
  email: string;
  company?: string;
  tags?: Array<{ id: string; name: string }>;
}

interface Tag {
  id: string;
  name: string;
}

interface StaticList {
  id: string;
  name: string;
  member_count: number;
}

interface AddContactsDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onAddContacts: (contactIds: string[]) => void;
}

export function AddContactsDialog({ isOpen, onClose, onAddContacts }: AddContactsDialogProps) {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [lists, setLists] = useState<StaticList[]>([]);
  const [selectedContacts, setSelectedContacts] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTag, setSelectedTag] = useState<string>('');
  const [selectedList, setSelectedList] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [abortController, setAbortController] = useState<AbortController | null>(null);

  // Debounced search effect
  useEffect(() => {
    if (!isOpen) return;

    const timer = setTimeout(() => {
      fetchContacts(1);
    }, 300);

    return () => clearTimeout(timer);
  }, [searchQuery, selectedTag, selectedList, isOpen]);

  // Fetch tags and lists on open
  useEffect(() => {
    if (isOpen) {
      fetchTags();
      fetchLists();
    } else {
      // Reset state on close
      setContacts([]);
      setSelectedContacts(new Set());
      setSearchQuery('');
      setSelectedTag('');
      setSelectedList('');
      setPage(1);
      setError(null);
    }
  }, [isOpen]);

  const fetchTags = async () => {
    try {
      const response = await api.get('/api/v1/tags');
      setTags(response.data.data || []);
    } catch (err) {
      console.error('Error fetching tags:', err);
    }
  };

  const fetchLists = async () => {
    try {
      const response = await api.get('/api/v1/lists');
      setLists(response.data.data || []);
    } catch (err) {
      console.error('Error fetching lists:', err);
    }
  };

  const fetchContacts = async (pageNum = 1) => {
    // Cancel previous request
    abortController?.abort();
    const controller = new AbortController();
    setAbortController(controller);

    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        page: pageNum.toString(),
        per_page: '50',
      });

      if (searchQuery) params.append('search', searchQuery);
      if (selectedTag) params.append('tag_id', selectedTag);
      if (selectedList) params.append('list_id', selectedList);

      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/v1/contacts?${params.toString()}`, {
        signal: controller.signal,
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      });

      if (!response.ok) {
        setError(`Failed to load contacts (${response.status})`);
        return;
      }

      const data = await response.json();
      setContacts(data.data || []);
      setTotal(data.total || 0);
      setPage(pageNum);
    } catch (err) {
      if (err instanceof Error && err.name !== 'AbortError') {
        setError('Network error. Please check your connection.');
        console.error('Error fetching contacts:', err);
      }
    } finally {
      setLoading(false);
    }
  };

  const toggleContactSelection = (contactId: string) => {
    const newSelected = new Set(selectedContacts);
    if (newSelected.has(contactId)) {
      newSelected.delete(contactId);
    } else {
      newSelected.add(contactId);
    }
    setSelectedContacts(newSelected);
  };

  const toggleSelectAll = () => {
    if (selectedContacts.size === contacts.length) {
      setSelectedContacts(new Set());
    } else {
      setSelectedContacts(new Set(contacts.map(c => c.id)));
    }
  };

  const handleAddContacts = () => {
    onAddContacts(Array.from(selectedContacts));
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[75vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Add Contacts to Campaign</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4 flex-1 overflow-hidden">
          {/* Filters */}
          <div className="grid grid-cols-3 gap-2">
            <Input
              type="text"
              placeholder="Search name, email, company..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="Search contacts"
            />
            <Select value={selectedTag} onValueChange={setSelectedTag}>
              <SelectTrigger aria-label="Filter by tag">
                <SelectValue placeholder="All Tags" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All Tags</SelectItem>
                {tags.map(tag => (
                  <SelectItem key={tag.id} value={tag.id}>{tag.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={selectedList} onValueChange={setSelectedList}>
              <SelectTrigger aria-label="Filter by list">
                <SelectValue placeholder="All Lists" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All Lists</SelectItem>
                {lists.map(list => (
                  <SelectItem key={list.id} value={list.id}>
                    {list.name} ({list.member_count})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          {/* Selection Controls */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={toggleSelectAll}
                disabled={contacts.length === 0}
              >
                {selectedContacts.size === contacts.length ? 'Clear All' : 'Select All'}
              </Button>
              <span className="text-sm text-gray-600">
                {selectedContacts.size} selected
              </span>
            </div>
            <span className="text-sm text-gray-600">
              Showing {contacts.length} of {total} contacts
            </span>
          </div>

          {/* Contacts Table */}
          <div className="flex-1 overflow-y-auto border rounded">
            {loading ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-gray-500">Loading contacts...</div>
              </div>
            ) : contacts.length === 0 ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-gray-500">No matching contacts found</div>
              </div>
            ) : (
              <table className="w-full">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="w-12 p-2"></th>
                    <th className="text-left p-2">Name</th>
                    <th className="text-left p-2">Email</th>
                    <th className="text-left p-2">Company</th>
                    <th className="text-left p-2">Tags</th>
                  </tr>
                </thead>
                <tbody>
                  {contacts.map(contact => (
                    <tr key={contact.id} className="border-t hover:bg-gray-50">
                      <td className="p-2">
                        <Checkbox
                          checked={selectedContacts.has(contact.id)}
                          onCheckedChange={() => toggleContactSelection(contact.id)}
                          aria-label={`Select contact ${contact.full_name || contact.email}`}
                        />
                      </td>
                      <td className="p-2">{contact.full_name || '—'}</td>
                      <td className="p-2">{contact.email}</td>
                      <td className="p-2">{contact.company || '—'}</td>
                      <td className="p-2">
                        {contact.tags && contact.tags.length > 0 ? (
                          <div className="flex gap-1 flex-wrap">
                            {contact.tags.map(tag => (
                              <span key={tag.id} className="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">
                                {tag.name}
                              </span>
                            ))}
                          </div>
                        ) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Pagination */}
          {total > 50 && (
            <div className="flex justify-between items-center">
              <div className="text-sm text-gray-600">
                Page {page} of {Math.ceil(total / 50)}
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => fetchContacts(page - 1)}
                  disabled={page <= 1 || loading}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => fetchContacts(page + 1)}
                  disabled={page * 50 >= total || loading}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button 
            onClick={handleAddContacts} 
            disabled={selectedContacts.size === 0}
          >
            Add Selected Contacts ({selectedContacts.size})
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
