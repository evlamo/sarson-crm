import { useState, useCallback } from 'react';
import type { FilterState } from '@/types/components';

/**
 * useFilterState hook - manage filter state for lists and tables
 * Used in: ContactsPage, ListsPage, and other filterable views
 * 
 * Encapsulates:
 * - Filter state management
 * - Filter clearing
 * - Filter resetting
 * 
 * @example
 * const { filters, setFilters, clearFilters } = useFilterState();
 */
export const useFilterState = (initialFilters?: Partial<FilterState>) => {
  const [filters, setFilters] = useState<FilterState>({
    search: '',
    tagIds: [],
    ...initialFilters,
  });

  const setFilter = useCallback(<K extends keyof FilterState>(
    key: K,
    value: FilterState[K]
  ) => {
    setFilters(prev => ({
      ...prev,
      [key]: value,
    }));
  }, []);

  const clearFilters = useCallback(() => {
    setFilters({
      search: '',
      tagIds: [],
    });
  }, []);

  const updateFilters = useCallback((newFilters: Partial<FilterState>) => {
    setFilters(prev => ({
      ...prev,
      ...newFilters,
    }));
  }, []);

  return {
    filters,
    setFilter,
    updateFilters,
    clearFilters,
  };
};

export default useFilterState;
