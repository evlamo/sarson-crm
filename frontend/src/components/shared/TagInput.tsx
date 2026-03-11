import React, { useState, useRef, useEffect } from 'react';
import { X, Plus } from 'lucide-react';
import type { TagInputProps } from '@/types/components';
import { Button } from '@/components/ui/button';

/**
 * TagInput component - multi-tag selector with create capability
 * Used across 4+ pages: ContactDetail, Contacts, Lists, Sheets, Campaigns
 * 
 * Supports:
 * - Add/remove tags
 * - Suggest tags
 * - Create new tags
 * - Max tags limit
 * 
 * @example
 * <TagInput
 *   tags={tags}
 *   onTagAdd={handleAdd}
 *   onTagRemove={handleRemove}
 *   suggestedTags={suggestions}
 *   maxTags={8}
 * />
 */
export const TagInput: React.FC<TagInputProps> = ({
  tags,
  onTagAdd,
  onTagRemove,
  suggestedTags = [],
  placeholder = 'Add a tag...',
  maxTags = 8,
  onCreateTag,
  isLoading = false
}) => {
  const [inputValue, setInputValue] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const canAddMore = maxTags === undefined || tags.length < maxTags;

  // Filter suggestions to exclude already-added tags
  const availableSuggestions = suggestedTags.filter(
    tag => !tags.find(t => t.id === tag.id)
  );

  const handleAddTag = (tag: { id: string; name: string; color?: string }) => {
    if (canAddMore) {
      onTagAdd(tag);
      setInputValue('');
      setShowSuggestions(false);
      inputRef.current?.focus();
    }
  };

  const handleCreateTag = async () => {
    if (!inputValue.trim() || !onCreateTag) return;

    setIsCreating(true);
    try {
      const newTag = await onCreateTag(inputValue.trim());
      handleAddTag(newTag);
    } catch (error) {
      console.error('Failed to create tag:', error);
    } finally {
      setIsCreating(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (inputValue.trim() && onCreateTag) {
        handleCreateTag();
      }
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
    }
  };

  // Close suggestions when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setShowSuggestions(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div ref={containerRef} className="space-y-2">
      {/* Selected tags */}
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {tags.map(tag => (
            <div
              key={tag.id}
              className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium ${
                tag.color || 'bg-gray-100 text-gray-700'
              }`}
            >
              <span>{tag.name}</span>
              <button
                onClick={() => onTagRemove(tag.id)}
                className="inline-flex items-center justify-center hover:opacity-70"
                aria-label={`Remove tag: ${tag.name}`}
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input and suggestions */}
      {canAddMore && (
        <div className="relative">
          <div className="flex items-center gap-2">
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={e => {
                setInputValue(e.target.value);
                setShowSuggestions(true);
              }}
              onKeyDown={handleKeyDown}
              onFocus={() => setShowSuggestions(true)}
              placeholder={placeholder}
              disabled={isLoading || isCreating}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            />
            {onCreateTag && inputValue.trim() && (
              <Button
                onClick={handleCreateTag}
                disabled={isCreating || isLoading}
                size="sm"
                variant="outline"
                className="gap-1"
              >
                <Plus className="w-4 h-4" />
                Create
              </Button>
            )}
          </div>

          {/* Suggestions dropdown */}
          {showSuggestions && availableSuggestions.length > 0 && (
            <div className="absolute top-full left-0 right-0 mt-2 bg-white border border-gray-300 rounded-lg shadow-lg z-50">
              <div className="py-2">
                {availableSuggestions.map(tag => (
                  <button
                    key={tag.id}
                    onClick={() => handleAddTag(tag)}
                    className="w-full text-left px-4 py-2 hover:bg-gray-100 flex items-center justify-between"
                  >
                    <span className="text-sm">{tag.name}</span>
                    <Plus className="w-4 h-4 text-gray-400" />
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Max tags reached message */}
      {!canAddMore && (
        <p className="text-sm text-gray-500">Max {maxTags} tags reached</p>
      )}
    </div>
  );
};

export default TagInput;
