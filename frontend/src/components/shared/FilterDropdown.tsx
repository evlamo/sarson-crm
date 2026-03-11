import React, { useState } from 'react';
import { ChevronDown, X } from 'lucide-react';
import type { FilterDropdownProps } from '@/types/components';
import { Button } from '@/components/ui/button';

/**
 * FilterDropdown component - multi-select filter with counts
 * Used across multiple pages: Contacts, Lists, Campaigns
 * 
 * @example
 * <FilterDropdown
 *   label="Status"
 *   options={statuses}
 *   selectedIds={selected}
 *   onSelectionChange={setSelected}
 *   showCounts={true}
 * />
 */
export const FilterDropdown: React.FC<FilterDropdownProps> = ({
  label,
  options,
  selectedIds,
  onSelectionChange,
  placeholder = 'Select...',
  isMulti = true,
  isLoading = false,
  showCounts = false
}) => {
  const [isOpen, setIsOpen] = useState(false);

  const handleSelect = (optionId: string) => {
    if (isMulti) {
      const newSelected = selectedIds.includes(optionId)
        ? selectedIds.filter(id => id !== optionId)
        : [...selectedIds, optionId];
      onSelectionChange(newSelected);
    } else {
      onSelectionChange([optionId]);
      setIsOpen(false);
    }
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    onSelectionChange([]);
  };

  const selectedLabels = options
    .filter(opt => selectedIds.includes(opt.id))
    .map(opt => opt.label)
    .join(', ');

  const displayText = selectedIds.length > 0 ? selectedLabels : placeholder;

  return (
    <div className="relative">
      <Button
        onClick={() => setIsOpen(!isOpen)}
        disabled={isLoading}
        variant="outline"
        className="w-full justify-between"
      >
        <span className="truncate">{label}: {displayText}</span>
        {selectedIds.length > 0 && (
          <X
            className="w-4 h-4 ml-2"
            onClick={handleClear}
          />
        )}
        <ChevronDown className={`w-4 h-4 ml-2 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </Button>

      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-white border border-gray-300 rounded-lg shadow-lg z-50">
          <div className="py-2 max-h-64 overflow-y-auto">
            {options.map(option => (
              <label
                key={option.id}
                className="flex items-center gap-3 px-4 py-2 hover:bg-gray-50 cursor-pointer"
              >
                <input
                  type={isMulti ? 'checkbox' : 'radio'}
                  name={isMulti ? undefined : label}
                  checked={selectedIds.includes(option.id)}
                  onChange={() => handleSelect(option.id)}
                  className="w-4 h-4"
                />
                <span className="flex-1 text-sm">{option.label}</span>
                {showCounts && option.count !== undefined && (
                  <span className="text-xs text-gray-500">({option.count})</span>
                )}
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default FilterDropdown;
