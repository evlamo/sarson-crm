import { useState, useCallback } from 'react';
import { MultiSelectState } from '@/types/components';

/**
 * useMultiSelectState hook - manage multi-select state for arrays
 * Used in: Tag selection, checkbox lists, bulk operations
 * 
 * Encapsulates:
 * - Toggle individual item selection
 * - Toggle all items at once
 * - Clear all selections
 * - Check if item is selected
 * - Get selection count
 * 
 * @example
 * const selection = useMultiSelectState<Contact>();
 * selection.toggle(contact.id);
 * selection.toggleAll(contacts);
 * selection.clear();
 */
export const useMultiSelectState = <T extends { id: string }>(
  initialSelected?: string[]
): MultiSelectState<T> => {
  const [selected, setSelected] = useState<Set<string>>(
    new Set(initialSelected || [])
  );

  const toggle = useCallback((id: string) => {
    setSelected(prev => {
      const newSet = new Set(prev);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else {
        newSet.add(id);
      }
      return newSet;
    });
  }, []);

  const toggleAll = useCallback((items: T[]) => {
    setSelected(prev => {
      const itemIds = new Set(items.map(i => i.id));
      const allSelected = items.length > 0 && items.every(i => prev.has(i.id));

      if (allSelected) {
        // Deselect all
        const newSet = new Set(prev);
        items.forEach(i => newSet.delete(i.id));
        return newSet;
      } else {
        // Select all
        return new Set([...prev, ...itemIds]);
      }
    });
  }, []);

  const clear = useCallback(() => {
    setSelected(new Set());
  }, []);

  const isSelected = useCallback((id: string) => {
    return selected.has(id);
  }, [selected]);

  return {
    selected,
    toggle,
    toggleAll,
    clear,
    isSelected,
    count: selected.size,
  };
};

export default useMultiSelectState;
