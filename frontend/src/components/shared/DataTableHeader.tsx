import React from 'react';
import { ArrowUpDown, ArrowUp, ArrowDown, Minus } from 'lucide-react';
import { DataTableHeaderProps } from '@/types/components';

/**
 * DataTableHeader component - table header with sorting and selection
 * Used in: Contacts, Campaign Lists, Sales Campaign Contacts, List Members
 * 
 * Supports:
 * - Column sorting (asc/desc)
 * - Bulk selection checkbox
 * - Column width customization
 * 
 * @example
 * <DataTableHeader
 *   columns={columns}
 *   sortColumn="name"
 *   sortOrder="asc"
 *   onSort={handleSort}
 *   hasCheckbox={true}
 *   onSelectAll={handleSelectAll}
 * />
 */
export const DataTableHeader: React.FC<DataTableHeaderProps> = ({
  columns,
  sortColumn,
  sortOrder,
  onSort,
  hasCheckbox = false,
  onSelectAll,
  isAllSelected = false
}) => {
  const getSortIcon = (columnKey: string) => {
    if (columnKey !== sortColumn) {
      return <ArrowUpDown className="w-4 h-4 text-gray-400" />;
    }

    if (sortOrder === 'asc') {
      return <ArrowUp className="w-4 h-4 text-blue-600" />;
    }

    return <ArrowDown className="w-4 h-4 text-blue-600" />;
  };

  return (
    <thead className="bg-gray-50 border-b border-gray-200">
      <tr>
        {hasCheckbox && (
          <th className="px-6 py-3 text-left">
            <input
              type="checkbox"
              checked={isAllSelected}
              onChange={e => onSelectAll?.(e.target.checked)}
              className="w-4 h-4 rounded border-gray-300"
            />
          </th>
        )}
        {columns.map(column => (
          <th
            key={column.key}
            className={`px-6 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider ${
              column.width ? `w-${column.width}` : ''
            } ${column.sortable ? 'cursor-pointer hover:bg-gray-100' : ''}`}
            style={column.width ? { width: column.width } : undefined}
            onClick={() => {
              if (column.sortable && onSort) {
                onSort(column.key);
              }
            }}
          >
            <div className="flex items-center gap-2">
              <span>{column.label}</span>
              {column.sortable && getSortIcon(column.key)}
            </div>
          </th>
        ))}
      </tr>
    </thead>
  );
};

export default DataTableHeader;
