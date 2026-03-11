/**
 * RecipientSelector - Campaign audience selection with live preview
 * 
 * Features:
 * - Select Lists (CampaignSegments) and Tags
 * - 500ms debounced live preview
 * - DNC exclusion breakdown (unsubscribed, bounced, invalid, no email)
 * - Source attribution per contact
 * - Combine mode toggle (ANY/ALL)
 * - Rate limit handling
 */
import { useState, useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Loader2, Users, AlertCircle, CheckCircle, Download, Search } from 'lucide-react';

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

interface ContactPreview {
  id: string;
  full_name: string;
  email: string | null;
  company: string | null;
  sources: string[];
}

interface ExclusionBreakdown {
  unsubscribed: number;
  bounced: number;
  invalid_email: number;
  no_email: number;
  total: number;
}

interface RecipientPreview {
  total_matching: number;
  exclusions: ExclusionBreakdown;
  final_count: number;
  page: number;
  per_page: number;
  total_pages: number;
  sample_contacts: ContactPreview[];
  breakdown: {
    from_lists: number;
    from_tags: number;
    overlap: number;
  };
}

interface RecipientSelectorProps {
  selectedListIds: string[];
  selectedTagIds: string[];
  combineMode: 'any' | 'all';
  onListsChange: (listIds: string[]) => void;
  onTagsChange: (tagIds: string[]) => void;
  onCombineModeChange: (mode: 'any' | 'all') => void;
  onPreviewChange?: (preview: RecipientPreview | null) => void;
}

// ── Debounce Hook ──────────────────────────────────────────────────────────

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(handler);
  }, [value, delay]);

  return debouncedValue;
}

// ── Main Component ─────────────────────────────────────────────────────────

export function RecipientSelector({
  selectedListIds,
  selectedTagIds,
  combineMode,
  onListsChange,
  onTagsChange,
  onCombineModeChange,
  onPreviewChange,
}: RecipientSelectorProps) {
  const [listSearch, setListSearch] = useState('');
  const [tagSearch, setTagSearch] = useState('');

  // Pagination and search for preview results
  const [previewPage, setPreviewPage] = useState(1);
  const [previewSearch, setPreviewSearch] = useState('');
  const debouncedPreviewSearch = useDebounce(previewSearch, 500);

  // 500ms debounce for preview API calls
  const debouncedListIds = useDebounce(selectedListIds, 500);
  const debouncedTagIds = useDebounce(selectedTagIds, 500);
  const debouncedCombineMode = useDebounce(combineMode, 500);

  // Fetch Lists (CampaignSegments)
  const { data: listsData } = useQuery<{ id: string; name: string; member_count: number }[]>({
    queryKey: ['campaign-lists'],
    queryFn: async () => {
      const res = await api.get('/campaign-lists');
      return res.data;
    },
    staleTime: 30000,
  });

  // Fetch Tags
  const { data: tagsData } = useQuery<Tag[]>({
    queryKey: ['tags'],
    queryFn: async () => {
      const res = await api.get('/tags');
      return res.data;
    },
    staleTime: 30000,
  });

  const lists: CampaignList[] = listsData || [];
  const tags: Tag[] = tagsData || [];

  // Filter Lists and Tags by search
  const filteredLists = useMemo(() => 
    lists.filter((list) =>
      list.name.toLowerCase().includes(listSearch.toLowerCase())
    ), [lists, listSearch]);

  const filteredTags = useMemo(() =>
    tags.filter((tag) =>
      tag.name.toLowerCase().includes(tagSearch.toLowerCase())
    ), [tags, tagSearch]);

  // Preview query - only fires when debounced values change
  const hasFilters = debouncedListIds.length > 0 || debouncedTagIds.length > 0;

  const {
    data: previewData,
    isLoading: previewLoading,
    error: previewError,
    isFetching: previewFetching,
  } = useQuery<{ data: RecipientPreview }>({
    queryKey: ['recipient-preview', debouncedListIds, debouncedTagIds, debouncedCombineMode, previewPage, debouncedPreviewSearch],
    queryFn: async () => {
      const res = await api.post('/campaigns/preview-recipients', {
        list_ids: debouncedListIds,
        tag_ids: debouncedTagIds,
        exclude_dnc: true,
        combine_mode: debouncedCombineMode,
        page: previewPage,
        per_page: 50,
        search: debouncedPreviewSearch || null,
      });
      return res.data;
    },
    enabled: hasFilters,
    staleTime: 10000,
    retry: (failureCount, error: any) => {
      // Don't retry on rate limit
      if (error?.response?.status === 429) return false;
      return failureCount < 2;
    },
  });

  const preview: RecipientPreview | null = previewData?.data || null;

  // Reset page when filters or search change
  useEffect(() => {
    setPreviewPage(1);
  }, [debouncedListIds, debouncedTagIds, debouncedCombineMode, debouncedPreviewSearch]);

  // Notify parent of preview changes
  useEffect(() => {
    onPreviewChange?.(preview);
  }, [preview, onPreviewChange]);

  // Check if rate limited
  const isRateLimited = (previewError as any)?.response?.status === 429;

  return (
    <div className="space-y-6">
      {/* Filter Selection Card */}
      <Card>
        <CardContent className="pt-6 space-y-6">
          {/* Lists Section */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <Label className="text-base font-semibold">Select Lists</Label>
              {selectedListIds.length > 0 && (
                <Badge variant="secondary">{selectedListIds.length} selected</Badge>
              )}
            </div>
            <p className="text-sm text-muted-foreground mb-3">
              Choose one or more lists to include in your campaign audience.
            </p>
            
            {/* Search - only show if more than 5 lists */}
            {lists.length > 5 && (
              <div className="relative mb-3">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search lists..."
                  value={listSearch}
                  onChange={(e) => setListSearch(e.target.value)}
                  className="pl-9"
                />
              </div>
            )}
            
            <div className="space-y-2 max-h-64 overflow-y-auto border rounded-lg p-2">
              {filteredLists.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">
                  {listSearch ? 'No lists match your search' : 'No lists available'}
                </p>
              ) : (
                filteredLists.map((list) => (
                  <label
                    key={list.id}
                    className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                      selectedListIds.includes(list.id)
                        ? 'border-[#253a52] bg-[#253a52]/5'
                        : 'border-transparent hover:border-gray-200 hover:bg-gray-50'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedListIds.includes(list.id)}
                      onChange={() => {
                        if (selectedListIds.includes(list.id)) {
                          onListsChange(selectedListIds.filter((id) => id !== list.id));
                        } else {
                          onListsChange([...selectedListIds, list.id]);
                        }
                      }}
                      className="w-4 h-4 rounded border-gray-300 text-[#253a52] focus:ring-[#253a52]"
                    />
                    <div className="flex-1 min-w-0">
                      <span className="text-sm font-medium truncate">{list.name}</span>
                      <span className="text-xs text-muted-foreground ml-2">
                        ({list.member_count?.toLocaleString() || 0} contacts)
                      </span>
                    </div>
                  </label>
                ))
              )}
            </div>
          </div>

          {/* Tags Section */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <Label className="text-base font-semibold">Select Tags</Label>
              {selectedTagIds.length > 0 && (
                <Badge variant="secondary">{selectedTagIds.length} selected</Badge>
              )}
            </div>
            <p className="text-sm text-muted-foreground mb-3">
              Optionally filter by tags to refine your audience.
            </p>
            
            {/* Search - only show if more than 10 tags */}
            {tags.length > 10 && (
              <div className="relative mb-3">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search tags..."
                  value={tagSearch}
                  onChange={(e) => setTagSearch(e.target.value)}
                  className="pl-9"
                />
              </div>
            )}
            
            <div className="flex flex-wrap gap-2 p-2 border rounded-lg min-h-[60px]">
              {filteredTags.length === 0 ? (
                <p className="text-sm text-muted-foreground w-full text-center py-2">
                  {tagSearch ? 'No tags match your search' : 'No tags available'}
                </p>
              ) : (
                filteredTags.map((tag) => (
                  <button
                    key={tag.id}
                    type="button"
                    onClick={() => {
                      if (selectedTagIds.includes(tag.id)) {
                        onTagsChange(selectedTagIds.filter((id) => id !== tag.id));
                      } else {
                        onTagsChange([...selectedTagIds, tag.id]);
                      }
                    }}
                    className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                      selectedTagIds.includes(tag.id)
                        ? 'bg-[#253a52] text-white border-[#253a52]'
                        : 'border-gray-300 hover:border-[#253a52]/50 hover:bg-gray-50'
                    }`}
                    style={tag.color && !selectedTagIds.includes(tag.id) ? { borderColor: tag.color } : undefined}
                  >
                    {tag.name}
                  </button>
                ))
              )}
            </div>
          </div>

          {/* Combine Mode - only show when both lists and tags selected */}
          {selectedListIds.length > 0 && selectedTagIds.length > 0 && (
            <div className="pt-4 border-t">
              <Label className="text-base font-semibold mb-3 block">Combine Mode</Label>
              <div className="flex gap-4">
                <label className={`flex items-center gap-2 p-3 rounded-lg border cursor-pointer flex-1 transition-colors ${
                  combineMode === 'any' ? 'border-[#253a52] bg-[#253a52]/5' : 'border-gray-200 hover:border-gray-300'
                }`}>
                  <input
                    type="radio"
                    name="combineMode"
                    value="any"
                    checked={combineMode === 'any'}
                    onChange={() => onCombineModeChange('any')}
                    className="text-[#253a52] focus:ring-[#253a52]"
                  />
                  <div>
                    <div className="font-medium text-sm">ANY (OR)</div>
                    <div className="text-xs text-muted-foreground">
                      Include contacts in any selected List or Tag
                    </div>
                  </div>
                </label>
                <label className={`flex items-center gap-2 p-3 rounded-lg border cursor-pointer flex-1 transition-colors ${
                  combineMode === 'all' ? 'border-[#253a52] bg-[#253a52]/5' : 'border-gray-200 hover:border-gray-300'
                }`}>
                  <input
                    type="radio"
                    name="combineMode"
                    value="all"
                    checked={combineMode === 'all'}
                    onChange={() => onCombineModeChange('all')}
                    className="text-[#253a52] focus:ring-[#253a52]"
                  />
                  <div>
                    <div className="font-medium text-sm">ALL (AND)</div>
                    <div className="text-xs text-muted-foreground">
                      Only contacts in all selected Lists and Tags
                    </div>
                  </div>
                </label>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Live Preview Card */}
      {(hasFilters || previewLoading) && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between mb-4">
              <Label className="text-base font-semibold">Audience Preview</Label>
              {preview && preview.final_count > 0 && (
                <Button variant="outline" size="sm" className="gap-2" disabled>
                  <Download className="h-4 w-4" />
                  Export CSV
                </Button>
              )}
            </div>


            {/* Search Input */}
            {preview && preview.final_count > 0 && (
              <div className="mb-4">
                <Input
                  placeholder="Search contacts by name, email, or company..."
                  value={previewSearch}
                  onChange={(e) => setPreviewSearch(e.target.value)}
                  className="w-full"
                />
              </div>
            )}
            {/* Loading State */}
            {(previewLoading || previewFetching) && (
              <div className="flex items-center justify-center py-8 text-muted-foreground">
                <Loader2 className="h-5 w-5 animate-spin mr-2" />
                Loading preview...
              </div>
            )}

            {/* Error State */}
            {previewError && !previewLoading && (
              <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg flex items-start gap-3">
                <AlertCircle className="h-5 w-5 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="font-medium">
                    {isRateLimited ? 'Rate Limit Exceeded' : 'Failed to load preview'}
                  </p>
                  <p className="text-sm mt-1">
                    {isRateLimited
                      ? 'Too many preview requests. Please wait a moment and try again.'
                      : 'Please try again or contact support if the issue persists.'}
                  </p>
                </div>
              </div>
            )}

            {/* Preview Results */}
            {preview && !previewLoading && !previewFetching && (
              <div className="space-y-4">
                {/* Summary Stats */}
                <div className="grid grid-cols-3 gap-3">
                  {/* Total Matching */}
                  <div className="bg-blue-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-blue-700">
                      {preview.total_matching.toLocaleString()}
                    </div>
                    <div className="text-xs text-blue-600 mt-1">Total Matching</div>
                    {preview.breakdown.overlap > 0 && (
                      <div className="text-xs text-blue-500 mt-1">
                        ({preview.breakdown.overlap.toLocaleString()} in both)
                      </div>
                    )}
                  </div>

                  {/* Excluded */}
                  {preview.exclusions.total > 0 && (
                    <div className="bg-amber-50 p-4 rounded-lg">
                      <div className="text-2xl font-bold text-amber-700">
                        {preview.exclusions.total.toLocaleString()}
                      </div>
                      <div className="text-xs text-amber-600 mt-1 space-y-0.5">
                        <div className="font-medium">Excluded:</div>
                        {preview.exclusions.unsubscribed > 0 && (
                          <div>• {preview.exclusions.unsubscribed} unsubscribed</div>
                        )}
                        {preview.exclusions.bounced > 0 && (
                          <div>• {preview.exclusions.bounced} bounced</div>
                        )}
                        {preview.exclusions.invalid_email > 0 && (
                          <div>• {preview.exclusions.invalid_email} invalid email</div>
                        )}
                        {preview.exclusions.no_email > 0 && (
                          <div>• {preview.exclusions.no_email} no email</div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Final Count */}
                  <div className={`p-4 rounded-lg ${
                    preview.final_count > 0 ? 'bg-green-50' : 'bg-red-50'
                  }`}>
                    <div className={`text-2xl font-bold flex items-center gap-1 ${
                      preview.final_count > 0 ? 'text-green-700' : 'text-red-700'
                    }`}>
                      {preview.final_count > 0 && <CheckCircle className="h-5 w-5" />}
                      {preview.final_count.toLocaleString()}
                    </div>
                    <div className={`text-xs mt-1 ${
                      preview.final_count > 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      Will Receive
                    </div>
                  </div>
                </div>

                {/* Sample Contacts */}
                {preview.sample_contacts.length > 0 && (
                  <div>
                    <p className="text-sm font-medium mb-2 text-muted-foreground">
                      Page {preview.page} of {preview.total_pages} ({preview.final_count.toLocaleString()} total):
                    </p>
                    <div className="space-y-2 max-h-80 overflow-y-auto">
                      {preview.sample_contacts.map((contact) => (
                        <div
                          key={contact.id}
                          className="p-3 bg-gray-50 rounded-lg"
                        >
                          <div className="flex items-center gap-2 flex-wrap">
                            <Users className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                            <span className="font-medium text-sm">{contact.full_name}</span>
                            {contact.email && (
                              <span className="text-muted-foreground text-sm">
                                ({contact.email})
                              </span>
                            )}
                            {contact.company && (
                              <Badge variant="outline" className="text-xs">
                                {contact.company}
                              </Badge>
                            )}
                          </div>
                          {contact.sources.length > 0 && (
                            <div className="text-xs text-muted-foreground mt-1 ml-6">
                              From: {contact.sources.join(', ')}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                    {/* Pagination Controls */}
                    {preview.total_pages > 1 && (
                      <div className="flex items-center justify-between mt-4 pt-4 border-t">
                        <div className="text-sm text-muted-foreground">
                          Page {preview.page} of {preview.total_pages}
                        </div>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setPreviewPage(p => Math.max(1, p - 1))}
                            disabled={preview.page === 1}
                          >
                            Previous
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setPreviewPage(p => Math.min(preview.total_pages, p + 1))}
                            disabled={preview.page === preview.total_pages}
                          >
                            Next
                          </Button>
                        </div>
                      </div>
                    )}
                )}

                {/* Warning if all excluded */}
                {preview.final_count === 0 && preview.total_matching > 0 && (
                  <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg">
                    <p className="font-medium flex items-center gap-2">
                      <AlertCircle className="h-4 w-4" />
                      All contacts excluded
                    </p>
                    <p className="text-sm mt-1">
                      Cannot send campaign. All {preview.total_matching.toLocaleString()} contacts are 
                      unsubscribed, bounced, or have invalid/missing emails.
                    </p>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Validation Message */}
      {!hasFilters && (
        <div className="bg-amber-50 border border-amber-200 text-amber-700 p-4 rounded-lg flex items-center gap-2">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span className="text-sm">
            Select at least one List or Tag to preview your audience
          </span>
        </div>
      )}
    </div>
  );
}

export default RecipientSelector;
