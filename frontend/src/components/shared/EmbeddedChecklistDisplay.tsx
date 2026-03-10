import React from 'react';
import { CheckCircle, AlertCircle, Info, XCircle } from 'lucide-react';
import { EmbeddedChecklistDisplayProps } from '@/types/components';

const typeIcons = {
  success: <CheckCircle className="w-5 h-5 text-green-600" />,
  warning: <AlertCircle className="w-5 h-5 text-yellow-600" />,
  error: <XCircle className="w-5 h-5 text-red-600" />,
  info: <Info className="w-5 h-5 text-blue-600" />,
};

const typeColors = {
  success: 'bg-green-50 border-green-200',
  warning: 'bg-yellow-50 border-yellow-200',
  error: 'bg-red-50 border-red-200',
  info: 'bg-blue-50 border-blue-200',
};

/**
 * EmbeddedChecklistDisplay component - reusable checklist display
 * Used in: Campaigns (send checklist), other validation checklists
 * 
 * @example
 * <EmbeddedChecklistDisplay 
 *   title="Send Checklist"
 *   items={checklist}
 *   compact={false}
 * />
 */
export const EmbeddedChecklistDisplay: React.FC<EmbeddedChecklistDisplayProps> = ({
  items,
  title,
  compact = false
}) => {
  return (
    <div className={`space-y-${compact ? '1' : '3'}`}>
      {title && (
        <h3 className={`font-semibold ${compact ? 'text-sm' : 'text-base'}`}>
          {title}
        </h3>
      )}
      <div className="space-y-2">
        {items.map(item => {
          const type = item.type || 'info';
          const icon = item.icon || typeIcons[type as keyof typeof typeIcons];
          const color = typeColors[type as keyof typeof typeColors];

          return (
            <div
              key={item.id}
              className={`flex items-start gap-${compact ? '2' : '3'} p-${compact ? '2' : '3'} rounded border ${color}`}
            >
              <div className="flex-shrink-0 mt-0.5">
                {icon}
              </div>
              <div className="flex-1">
                <p className={`${compact ? 'text-sm' : 'text-base'}`}>
                  {item.label}
                </p>
              </div>
              {item.completed && (
                <div className="text-green-600">✓</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default EmbeddedChecklistDisplay;
