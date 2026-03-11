import { useState, useCallback } from 'react';
import type { TableState } from '@/types/components';

/**
 * useTableState hook - manage table pagination, sorting, and selection
 * Used in: ContactsTable, CampaignsList, all data tables
 * 
 * Encapsulates:
 * - Pagination (page, pageSize)
 * - Sorting (sortColumn, sortOrder)
 * - Bulk selection (selectedIds)
 * 
 * @example
 * const table = useTableState();
 * table.setPage(2);
 * table.setSort('name', 'asc');
 * table.toggleSelection('id-123');
 */
export const useTableState = (initialPageSize: number = 50) => {
  const [state, setState] = useState<TableState>({
    page: 1,
    pageSize: initialPageSize,
    sortColumn: undefined,
    sortOrder: undefined,
    selectedIds: new Set(),
  });

  const setPage = useCallback((page: number) => {
    setState(prev => ({ ...prev, page, selectedIds: new Set() }));
  }, []);

  const setPageSize = useCallback((pageSize: number) => {
    setState(prev => ({ ...prev, pageSize, page: 1 }));
  }, []);

  const setSort = useCallback((column: string, order?: 'asc' | 'desc') => {
    setState(prev => ({
      ...prev,
      sortColumn: column,
      sortOrder: order || (prev.sortColumn === column && prev.sortOrder === 'asc' ? 'desc' : 'asc'),
    }));
  }, []);

  const toggleSelection = useCallback((id: string) => {
    setState(prev => {
      const newSelected = new Set(prev.selectedIds);
      if (newSelected.has(id)) {
        newSelected.delete(id);
      } else {
        newSelected.add(id);
      }
      return { ...prev, selectedIds: newSelected };
    });
  }, []);

  const toggleAllSelection = useCallback((ids: string[]) => {
    setState(prev => {
      const newSelected = new Set(prev.selectedIds);
      if (newSelected.size === ids.length) {
        // All are selected, deselect all
        newSelected.clear();
      } else {
        // Not all selected, select all
        ids.forEach(id => newSelected.add(id));
      }
      return { ...prev, selectedIds: newSelected };
    });
  }, []);

  const clearSelection = useCallback(() => {
    setState(prev => ({ ...prev, selectedIds: new Set() }));
  }, []);

  return {
    ...state,
    setPage,
    setPageSize,
    setSort,
    toggleSelection,
    toggleAllSelection,
    clearSelection,
    isSelected: (id: string) => state.selectedIds.has(id),
    selectionCount: state.selectedIds.size,
  };
};

export default useTableState;
