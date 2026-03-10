import React from 'react';
import { StatusBadgeProps } from '@/types/components';

const statusColors: Record<string, { bg: string; text: string; border: string }> = {
  active: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' },
  inactive: { bg: 'bg-gray-50', text: 'text-gray-700', border: 'border-gray-200' },
  pending: { bg: 'bg-yellow-50', text: 'text-yellow-700', border: 'border-yellow-200' },
  draft: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
  sent: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' },
  scheduled: { bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200' },
  failed: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
  paused: { bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200' },
  excluded: { bg: 'bg-gray-50', text: 'text-gray-700', border: 'border-gray-200' },
  completed: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' },
  'out-of-sync': { bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200' },
  synced: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' },
};

/**
 * StatusBadge component - displays a color-coded status indicator
 * Used across 5+ pages: Campaigns, Contacts, SalesCampaigns, ContactDetail, Lists
 * 
 * @example
 * <StatusBadge status="active" />
 * <StatusBadge status="draft" variant="outline" />
 */
export const StatusBadge: React.FC<StatusBadgeProps> = ({ 
  status, 
  variant = 'default',
  className = ''
}) => {
  const colors = statusColors[status.toLowerCase()] || statusColors.pending;
  const displayStatus = status.charAt(0).toUpperCase() + status.slice(1).replace(/-/g, ' ');
  
  if (variant === 'outline') {
    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${colors.border} ${colors.text} ${className}`}>
        {displayStatus}
      </span>
    );
  }
  
  if (variant === 'sm') {
    return (
      <span className={`inline-block w-2 h-2 rounded-full ${colors.bg.replace('bg-', 'bg-')} ${className}`} />
    );
  }
  
  // default variant
  return (
    <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium ${colors.bg} ${colors.text} ${className}`}>
      {displayStatus}
    </span>
  );
};

export default StatusBadge;
