/**
 * Single source of truth for contact status definitions.
 * Import this everywhere statuses are displayed or selected.
 */

export interface StatusDef {
  value: string;
  label: string;
  dot: string;       // Tailwind bg class for the dot indicator
  badge: string;     // Tailwind classes for pill/badge display
}

export const STATUSES: StatusDef[] = [
  { value: 'hot',      label: 'Hot',      dot: 'bg-red-500',    badge: 'bg-red-100 text-red-700 border-red-200' },
  { value: 'warm',     label: 'Warm',     dot: 'bg-orange-400', badge: 'bg-orange-100 text-orange-700 border-orange-200' },
  { value: 'prospect', label: 'Prospect', dot: 'bg-yellow-400', badge: 'bg-yellow-100 text-yellow-700 border-yellow-200' },
  { value: 'cold',     label: 'Cold',     dot: 'bg-blue-400',   badge: 'bg-blue-100 text-blue-600 border-blue-200' },
  { value: 'poc',      label: 'POC',      dot: 'bg-purple-500', badge: 'bg-purple-100 text-purple-700 border-purple-200' },
  { value: 'active',   label: 'Active',   dot: 'bg-green-500',  badge: 'bg-green-100 text-green-700 border-green-200' },
  { value: 'na',       label: 'N/A',      dot: 'bg-gray-300',   badge: 'bg-gray-100 text-gray-500 border-gray-200' },
];

export const STATUS_MAP = Object.fromEntries(STATUSES.map((s) => [s.value, s]));

export function getStatus(value: string | null | undefined): StatusDef {
  return STATUS_MAP[value ?? ''] ?? { value: value ?? '', label: capitalize(value ?? '—'), dot: 'bg-gray-300', badge: 'bg-gray-100 text-gray-500 border-gray-200' };
}

/** Capitalize first letter, lowercase rest. Handles null/undefined. */
export function capitalize(s: string): string {
  if (!s) return '';
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
}
