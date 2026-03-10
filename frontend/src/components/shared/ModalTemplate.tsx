import React from 'react';
import { X } from 'lucide-react';
import { ModalTemplateProps } from '@/types/components';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';

const sizeClasses = {
  sm: 'sm:max-w-md',
  md: 'sm:max-w-lg',
  lg: 'sm:max-w-2xl',
  xl: 'sm:max-w-4xl',
};

/**
 * ModalTemplate component - reusable dialog/modal wrapper
 * Used across: Campaigns, Contacts, SalesCampaigns, Lists, and custom modals
 * 
 * Provides consistent modal styling and structure
 * 
 * @example
 * <ModalTemplate
 *   isOpen={open}
 *   onClose={handleClose}
 *   title="Create Campaign"
 *   description="Fill in the campaign details"
 *   size="lg"
 * >
 *   <form>{children}</form>
 *   <DialogFooter>...</DialogFooter>
 * </ModalTemplate>
 */
export const ModalTemplate: React.FC<ModalTemplateProps> = ({
  isOpen,
  onClose,
  title,
  description,
  children,
  footer,
  size = 'md',
  isLoading = false,
  isDangerous = false
}) => {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent
        className={`${sizeClasses[size]} ${
          isDangerous ? 'border-red-200' : ''
        }`}
      >
        <DialogHeader>
          <DialogTitle className={isDangerous ? 'text-red-600' : ''}>
            {title}
          </DialogTitle>
          {description && (
            <DialogDescription>
              {description}
            </DialogDescription>
          )}
        </DialogHeader>

        <div className={`py-4 ${isLoading ? 'opacity-50 pointer-events-none' : ''}`}>
          {children}
        </div>

        {footer && (
          <DialogFooter>
            {footer}
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default ModalTemplate;
