import React from 'react';
import { Check, AlertCircle } from 'lucide-react';
import type { StepIndicatorProps } from '@/types/components';

/**
 * StepIndicator component - multi-step form step navigator
 * Used in: Campaigns (5 steps), Lists (3 steps), other multi-step forms
 * 
 * Supports:
 * - Vertical or horizontal layout
 * - Step completion tracking
 * - Error state indication
 * - Click-to-navigate (editable mode)
 * 
 * @example
 * <StepIndicator
 *   steps={steps}
 *   activeStep="step2"
 *   onStepClick={handleStepClick}
 *   editable={true}
 * />
 */
export const StepIndicator: React.FC<StepIndicatorProps> = ({
  steps,
  activeStep,
  onStepClick,
  vertical = false,
  editable = false
}) => {
  const activeIndex = steps.findIndex(s => s.id === activeStep);

  return (
    <div className={`flex ${vertical ? 'flex-col' : 'flex-row items-center'} gap-4`}>
      {steps.map((step, index) => {
        const isActive = step.id === activeStep;
        const isCompleted = step.completed || index < activeIndex;
        const canNavigate = editable && (isCompleted || index <= activeIndex);

        return (
          <React.Fragment key={step.id}>
            {/* Step indicator */}
            <div
              className={`flex flex-col ${vertical ? '' : 'items-center'} gap-2 cursor-pointer`}
              onClick={() => canNavigate && onStepClick?.(step.id)}
              role="button"
              tabIndex={canNavigate ? 0 : -1}
              onKeyDown={(e) => {
                if (canNavigate && (e.key === 'Enter' || e.key === ' ')) {
                  onStepClick?.(step.id);
                }
              }}
            >
              <div
                className={`flex items-center justify-center w-10 h-10 rounded-full font-semibold transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white'
                    : isCompleted
                    ? 'bg-green-600 text-white'
                    : step.error
                    ? 'bg-red-100 text-red-700'
                    : 'bg-gray-200 text-gray-700'
                } ${canNavigate && !isActive ? 'hover:bg-blue-500' : ''}`}
              >
                {isCompleted && !isActive ? (
                  <Check className="w-5 h-5" />
                ) : step.error ? (
                  <AlertCircle className="w-5 h-5" />
                ) : (
                  <span>{index + 1}</span>
                )}
              </div>
              <span
                className={`text-sm font-medium ${
                  isActive ? 'text-blue-600' : isCompleted ? 'text-green-600' : 'text-gray-700'
                }`}
              >
                {step.label}
              </span>
              {step.error && (
                <span className="text-xs text-red-600">Error</span>
              )}
            </div>

            {/* Connector line (except last step) */}
            {index < steps.length - 1 && (
              <div
                className={`${
                  vertical
                    ? 'w-1 h-8 mx-5'
                    : 'flex-1 h-1'
                } ${
                  isCompleted ? 'bg-green-600' : 'bg-gray-300'
                } transition-colors`}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};

export default StepIndicator;
