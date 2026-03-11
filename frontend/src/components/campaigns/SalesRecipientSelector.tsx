/**
 * SalesRecipientSelector - Advanced campaign audience selection modal
 * 
 * Features:
 * - Large modal (90vw x 85vh) with split layout
 * - Multi-select for Lists, Tags, and Individual Contacts
 * - 500ms debounced live preview
 * - DNC exclusion breakdown
 * - Source attribution per contact
 * - Combine mode toggle (ANY/ALL)
 * - Sample contacts display (first 10)
 * - Breakdown stats (from_lists, from_tags, from_direct, overlap)
 */

import { useState, useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { debounce } from 'lodash';
import api from '@/lib/api';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Loader2, AlertCircle, Users, Search, X } from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────────────

interface CampaignList {
  id: string;
  name: string;
  member_count: number;
}

interface Tag {
  id: string;
  name: string;
  color?: string;
  contact_count?: number;
}

interface AvailableContact {
  id: string;
  full_name: string;
  email: string;
  company?: string;
}

interface ContactPreview {
  id: string;
  full_name: string;
  email: string;
  company?: string;
  sources: string[];
}

interface ExclusionBreakdown {
  unsubscribed: number;
  bounced: number;
  invalid_email: number;
  no_email: number;
  already_in_campaign: number;
  total: number;
}

interface PreviewResponse {
  total_matching: number;
  exclusions: ExclusionBreakdown;
  final_count: number;
  sample_contacts: ContactPreview[];
  breakdown: {
    from_lists: number;
    from_tags: number;
    from_direct: number;
    overlap: number;
  };
}

interface SalesRecipientSelectorProps {
  campaignId: string;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (contactIds: string[]) => void;
}

// ── Main Component ─────────────────────────────────────────────────────────

export function SalesRecipientSelector({
  campaignId,
  isOpen,
  onClose,
  onConfirm,
}: SalesRecipientSelectorProps) {
  // State
  const [selectedListIds, setSelectedListIds] = useState<string[]>([]);
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);
  const [selectedContactIds, setSelectedContactIds] = useState<string[]>([]);
  const [combineMode, setCombineMode] = useState<'any' | 'all'>('any');
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);

  const [listSearch, setListSearch] = useState('');
  const [tagSearch, setTagSearch] = useState('');
  const [contactSearch, setContactSearch] = useState('');

  // Fetch lists
  const { data: listsData } = useQuery<CampaignList[]>({
    queryKey: ['campaign-lists'],
    queryFn: async () => {
      const res = await api.get('/lists');
      return res.data.data || [];
    },
    staleTime: 30000,
    enabled: isOpen,
  });

  // Fetch tags
  const { data: tagsData } = useQuery<Tag[]>({
    queryKey: ['tags'],
    queryFn: async () => {
      const res = await api.get('/tags');
      return res.data;
    },
    staleTime: 30000,
    enabled: isOpen,
  });

  // Fetch available contacts
  const { data: contactsData } = useQuery<AvailableContact[]>({
    queryKey: ['campaign-available-contacts', campaignId],
    queryFn: async () => {
      const res = await api.get(
        `/sales-campaigns/${campaignId}/available-contacts`,
        {
          params: { per_page: 100 },
        }
      );
      return res.data.data?.contacts || [];
    },
    staleTime: 30000,
    enabled: isOpen && !!campaignId,
  });

  const lists = listsData || [];
  const tags = tagsData || [];
  const contacts = contactsData || [];

  // Filter lists and tags by search
  const filteredLists = useMemo(
    () =>
      lists.filter((list) =>
        list.name.toLowerCase().includes(listSearch.toLowerCase())
      ),
    [lists, listSearch]
  );

  const filteredTags = useMemo(
    () =>
      tags.filter((tag) =>
        tag.name.toLowerCase().includes(tagSearch.toLowerCase())
      ),
    [tags, tagSearch]
  );

  const filteredContacts = useMemo(
    () =>
      contacts.filter(
        (contact) =>
          contact.full_name.toLowerCase().includes(contactSearch.toLowerCase()) ||
          contact.email.toLowerCase().includes(contactSearch.toLowerCase())
      ),
    [contacts, contactSearch]
  );

  // Debounced preview fetch
  const debouncedFetchPreview = useMemo(
    () =>
      debounce(async () => {
        if (
          !selectedListIds.length &&
          !selectedTagIds.length &&
          !selectedContactIds.length
        ) {
          setPreview(null);
          return;
        }

        setIsLoadingPreview(true);
        try {
          const res = await api.post(
            `/sales-campaigns/${campaignId}/preview-recipients`,
            {
              list_ids: selectedListIds,
              tag_ids: selectedTagIds,
              contact_ids: selectedContactIds,
              combine_mode: combineMode,
            }
          );
          setPreview(res.data.data);
        } catch (err: any) {
          console.error('Preview failed:', err);
          toast.error(err.response?.data?.detail || 'Failed to load preview');
          setPreview(null);
        } finally {
          setIsLoadingPreview(false);
        }
      }, 500),
    [campaignId, selectedListIds, selectedTagIds, selectedContactIds, combineMode]
  );

  // Trigger preview on selection change
  useEffect(() => {
    debouncedFetchPreview();
    return () => debouncedFetchPreview.cancel();
  }, [debouncedFetchPreview]);

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setSelectedListIds([]);
      setSelectedTagIds([]);
      setSelectedContactIds([]);
      setCombineMode('any');
      setPreview(null);
      setListSearch('');
      setTagSearch('');
      setContactSearch('');
    }
  }, [isOpen]);

  const handleConfirm = () => {
    if (!preview || preview.final_count === 0) {
      toast.error('No contacts to add');
      return;
    }

    // Send all contact IDs from preview
    const contactIds = preview.sample_contacts.map((c) => c.id);
    onConfirm(contactIds);
    onClose();
  };

  const toggleList = (listId: string) => {
    setSelectedListIds((prev) =>
      prev.includes(listId)
        ? prev.filter((id) => id !== listId)
        : [...prev, listId]
    );
  };

  const toggleTag = (tagId: string) => {
    setSelectedTagIds((prev) =>
      prev.includes(tagId)
        ? prev.filter((id) => id !== tagId)
        : [...prev, tagId]
    );
  };

  const toggleContact = (contactId: string) => {
    setSelectedContactIds((prev) =>
      prev.includes(contactId)
        ? prev.filter((id) => id !== contactId)
        : [...prev, contactId]
    );
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-[98vw] max-h-[90vh] overflow-hidden flex flex-col p-0">
        <DialogHeader className="px-6 py-4 border-b">
          <DialogTitle>Add Contacts to Campaign</DialogTitle>
        </DialogHeader>

        <div className="grid grid-cols-[35%_65%] gap-6 flex-1 overflow-hidden px-6 py-4">
          {/* Left Panel: Selection Controls */}
          <div className="space-y-4 overflow-y-auto pr-2">
            {/* Lists Multi-Select */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <Label className="text-sm font-semibold">Select Lists</Label>
                {selectedListIds.length > 0 && (
                  <Badge variant="secondary" className="text-xs">
                    {selectedListIds.length}
                  </Badge>
                )}
              </div>

              {filteredLists.length > 0 && (
                <div className="relative mb-2">
                  <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search lists..."
                    value={listSearch}
                    onChange={(e) => setListSearch(e.target.value)}
                    className="pl-8 h-8 text-sm"
                  />
                </div>
              )}

              <div className="space-y-1 max-h-32 overflow-y-auto border rounded p-2">
                {filteredLists.length === 0 ? (
                  <p className="text-xs text-muted-foreground text-center py-2">
                    {listSearch ? 'No lists match' : 'No lists available'}
                  </p>
                ) : (
                  filteredLists.map((list) => (
                    <label
                      key={list.id}
                      className={`flex items-center gap-2 p-2 rounded cursor-pointer text-sm transition-colors ${
                        selectedListIds.includes(list.id)
                          ? 'bg-blue-50'
                          : 'hover:bg-gray-50'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedListIds.includes(list.id)}
                        onChange={() => toggleList(list.id)}
                        className="w-4 h-4 rounded"
                      />
                      <span className="flex-1 truncate">{list.name}</span>
                      <span className="text-xs text-muted-foreground">
                        ({list.member_count})
                      </span>
                    </label>
                  ))
                )}
              </div>
            </div>

            {/* Tags Multi-Select */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <Label className="text-sm font-semibold">Select Tags</Label>
                {selectedTagIds.length > 0 && (
                  <Badge variant="secondary" className="text-xs">
                    {selectedTagIds.length}
                  </Badge>
                )}
              </div>

              {filteredTags.length > 0 && (
                <div className="relative mb-2">
                  <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search tags..."
                    value={tagSearch}
                    onChange={(e) => setTagSearch(e.target.value)}
                    className="pl-8 h-8 text-sm"
                  />
                </div>
              )}

              <div className="flex flex-wrap gap-2 p-2 border rounded min-h-10">
                {filteredTags.length === 0 ? (
                  <p className="text-xs text-muted-foreground w-full text-center py-1">
                    {tagSearch ? 'No tags match' : 'No tags available'}
                  </p>
                ) : (
                  filteredTags.map((tag) => (
                    <button
                      key={tag.id}
                      onClick={() => toggleTag(tag.id)}
                      className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                        selectedTagIds.includes(tag.id)
                          ? 'bg-blue-600 text-white border-blue-600'
                          : 'border-gray-300 hover:border-blue-300 hover:bg-blue-50'
                      }`}
                    >
                      {tag.name}
                    </button>
                  ))
                )}
              </div>
            </div>

            {/* Individual Contacts Multi-Select */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <Label className="text-sm font-semibold">Select Contacts</Label>
                {selectedContactIds.length > 0 && (
                  <Badge variant="secondary" className="text-xs">
                    {selectedContactIds.length}
                  </Badge>
                )}
              </div>

              {contacts.length > 0 && (
                <div className="relative mb-2">
                  <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search contacts..."
                    value={contactSearch}
                    onChange={(e) => setContactSearch(e.target.value)}
                    className="pl-8 h-8 text-sm"
                  />
                </div>
              )}

              <div className="space-y-1 max-h-32 overflow-y-auto border rounded p-2">
                {contacts.length === 0 ? (
                  <p className="text-xs text-muted-foreground text-center py-2">
                    No contacts available
                  </p>
                ) : filteredContacts.length === 0 ? (
                  <p className="text-xs text-muted-foreground text-center py-2">
                    No contacts match
                  </p>
                ) : (
                  filteredContacts.map((contact) => (
                    <label
                      key={contact.id}
                      className={`flex items-center gap-2 p-2 rounded cursor-pointer text-sm transition-colors ${
                        selectedContactIds.includes(contact.id)
                          ? 'bg-blue-50'
                          : 'hover:bg-gray-50'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedContactIds.includes(contact.id)}
                        onChange={() => toggleContact(contact.id)}
                        className="w-4 h-4 rounded"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium truncate">
                          {contact.full_name}
                        </div>
                        <div className="text-xs text-muted-foreground truncate">
                          {contact.email}
                        </div>
                      </div>
                    </label>
                  ))
                )}
              </div>
            </div>

            {/* Combine Mode */}
            <div className="pt-4 border-t">
              <Label className="text-sm font-semibold block mb-3">Combine Mode</Label>
              <div className="space-y-2">
                <label className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                  combineMode === 'any'
                    ? 'border-blue-600 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}>
                  <input
                    type="radio"
                    name="combineMode"
                    value="any"
                    checked={combineMode === 'any'}
                    onChange={() => setCombineMode('any')}
                    className="w-4 h-4 text-blue-600"
                  />
                  <div>
                    <div className="font-medium text-sm">Any (OR)</div>
                    <div className="text-xs text-muted-foreground">
                      Include contacts matching any selection
                    </div>
                  </div>
                </label>
                <label className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                  combineMode === 'all'
                    ? 'border-blue-600 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}>
                  <input
                    type="radio"
                    name="combineMode"
                    value="all"
                    checked={combineMode === 'all'}
                    onChange={() => setCombineMode('all')}
                    className="w-4 h-4 text-blue-600"
                  />
                  <div>
                    <div className="font-medium text-sm">All (AND)</div>
                    <div className="text-xs text-muted-foreground">
                      Only contacts matching all selections
                    </div>
                  </div>
                </label>
              </div>
            </div>
          </div>

          {/* Right Panel: Live Preview */}
          <div className="border rounded-lg p-4 overflow-y-auto bg-slate-50">
            {isLoadingPreview ? (
              <div className="flex items-center justify-center h-32">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="text-sm">Loading preview...</span>
                </div>
              </div>
            ) : preview ? (
              <div className="space-y-4">
                {/* Header */}
                <div>
                  <div className="text-3xl font-bold text-green-700">
                    {preview.final_count.toLocaleString()}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    contacts will be added
                  </div>
                </div>

                {/* Exclusions Banner */}
                {preview.exclusions.total > 0 && (
                  <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                    <div className="font-medium text-yellow-900 text-sm mb-1">
                      {preview.exclusions.total.toLocaleString()} contacts excluded
                    </div>
                    <ul className="text-yellow-700 space-y-0.5 text-xs">
                      {preview.exclusions.unsubscribed > 0 && (
                        <li>• {preview.exclusions.unsubscribed} unsubscribed</li>
                      )}
                      {preview.exclusions.bounced > 0 && (
                        <li>• {preview.exclusions.bounced} bounced</li>
                      )}
                      {preview.exclusions.invalid_email > 0 && (
                        <li>• {preview.exclusions.invalid_email} invalid email</li>
                      )}
                      {preview.exclusions.no_email > 0 && (
                        <li>• {preview.exclusions.no_email} no email</li>
                      )}
                      {preview.exclusions.already_in_campaign > 0 && (
                        <li>• {preview.exclusions.already_in_campaign} already in campaign</li>
                      )}
                    </ul>
                  </div>
                )}

                {/* Sample Contacts */}
                {preview.sample_contacts.length > 0 && (
                  <div>
                    <div className="text-sm font-medium mb-2 text-muted-foreground">
                      Sample Contacts (first {preview.sample_contacts.length}):
                    </div>
                    <div className="space-y-2">
                      {preview.sample_contacts.map((contact) => (
                        <div
                          key={contact.id}
                          className="text-sm p-2 bg-white rounded border border-gray-200"
                        >
                          <div className="font-medium">{contact.full_name}</div>
                          <div className="text-xs text-muted-foreground">
                            {contact.email}
                          </div>
                          {contact.company && (
                            <div className="text-xs text-muted-foreground">
                              {contact.company}
                            </div>
                          )}
                          {contact.sources.length > 0 && (
                            <div className="text-xs text-blue-600 mt-1">
                              {contact.sources.join(', ')}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                    {preview.final_count > preview.sample_contacts.length && (
                      <div className="text-xs text-muted-foreground mt-2">
                        + {preview.final_count - preview.sample_contacts.length} more
                      </div>
                    )}
                  </div>
                )}

                {/* Breakdown */}
                <div className="text-xs text-muted-foreground pt-4 border-t space-y-1">
                  <div>From Lists: {preview.breakdown.from_lists}</div>
                  <div>From Tags: {preview.breakdown.from_tags}</div>
                  <div>From Direct: {preview.breakdown.from_direct}</div>
                  {preview.breakdown.overlap > 0 && (
                    <div>Overlap: {preview.breakdown.overlap}</div>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center h-32">
                <div className="text-center">
                  <Users className="h-8 w-8 mx-auto mb-2 text-muted-foreground opacity-50" />
                  <p className="text-sm text-muted-foreground">
                    Select lists, tags, or contacts to preview
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        <DialogFooter className="px-6 py-4 border-t">
          <Button onClick={onClose} variant="outline">
            Cancel
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={!preview || preview.final_count === 0 || isLoadingPreview}
          >
            Add {preview?.final_count || 0} Contacts
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default SalesRecipientSelector;
