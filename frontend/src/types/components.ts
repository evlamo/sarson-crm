// Shared component prop interfaces for Phase C decomposition

// Status Badge Component
export interface StatusBadgeProps {
  status: string;
  variant?: 'default' | 'outline' | 'sm';
  className?: string;
}

// Tag Input Component
export interface TagInputProps {
  tags: Array<{ id: string; name: string; color?: string }>;
  onTagAdd: (tag: { id: string; name: string; color?: string }) => void;
  onTagRemove: (tagId: string) => void;
  suggestedTags?: Array<{ id: string; name: string; color?: string }>;
  placeholder?: string;
  maxTags?: number;
  onCreateTag?: (name: string) => Promise<{ id: string; name: string; color?: string }>;
  isLoading?: boolean;
}

// Filter Dropdown Component
export interface FilterOption {
  id: string;
  label: string;
  count?: number;
}

export interface FilterDropdownProps {
  label: string;
  options: FilterOption[];
  selectedIds: string[];
  onSelectionChange: (selectedIds: string[]) => void;
  placeholder?: string;
  isMulti?: boolean;
  isLoading?: boolean;
  showCounts?: boolean;
}

// Embedded Checklist Display
export interface ChecklistItem {
  id: string;
  label: string;
  completed: boolean;
  type?: 'info' | 'success' | 'warning' | 'error';
  icon?: React.ReactNode;
}

export interface EmbeddedChecklistDisplayProps {
  items: ChecklistItem[];
  title?: string;
  compact?: boolean;
}

// Data Table Header Component
export interface DataTableHeaderProps {
  columns: Array<{
    key: string;
    label: string;
    sortable?: boolean;
    width?: string;
  }>;
  sortColumn?: string;
  sortOrder?: 'asc' | 'desc';
  onSort?: (column: string) => void;
  hasCheckbox?: boolean;
  onSelectAll?: (selected: boolean) => void;
  isAllSelected?: boolean;
}

// Modal Template Component
export interface ModalTemplateProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  isLoading?: boolean;
  isDangerous?: boolean;
}

// Step Indicator Component
export interface Step {
  id: string;
  label: string;
  completed?: boolean;
  error?: boolean;
}

export interface StepIndicatorProps {
  steps: Step[];
  activeStep: string;
  onStepClick?: (stepId: string) => void;
  vertical?: boolean;
  editable?: boolean;
}

// Filter State Hook
export interface FilterState {
  search: string;
  status?: string;
  repId?: string;
  segmentId?: string;
  listId?: string;
  tagIds: string[];
}

// Modal State Hook
export interface ModalState {
  isOpen: boolean;
  data?: Record<string, unknown>;
}

// Table State Hook
export interface TableState {
  page: number;
  pageSize: number;
  sortColumn?: string;
  sortOrder?: 'asc' | 'desc';
  selectedIds: Set<string>;
}

// Campaign Form State Hook
export interface CampaignFormState {
  name: string;
  subject: string;
  previewText: string;
  fromEmail: string;
  fromName: string;
  replyTo: string;
  templateId: string | null;
  bodyHtml: string;
  bodyText: string;
  campaignListIds: string[];
  segmentId?: string;
  tagIds: string[];
  trackingOpens: boolean;
  trackingClicks: boolean;
  timewarp: boolean;
  gaTag?: string;
}

// Multi-Select State Hook
export interface MultiSelectState<T> {
  selected: Set<string>;
  toggle: (id: string) => void;
  toggleAll: (items: T[]) => void;
  clear: () => void;
  isSelected: (id: string) => boolean;
  count: number;
}
