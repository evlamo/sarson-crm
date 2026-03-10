import { useState, useCallback } from 'react';
import { ModalState } from '@/types/components';

/**
 * useModalState hook - manage modal open/close state with optional data
 * Used in: Create/Edit/Delete dialogs across all pages
 * 
 * Encapsulates:
 * - Modal open/close logic
 * - Data passing between parent and modal
 * - Modal state reset
 * 
 * @example
 * const modal = useModalState();
 * modal.open({ id: '123', name: 'Test' });
 * modal.close();
 */
export const useModalState = <T extends Record<string, unknown> = Record<string, unknown>>(
  initialData?: T
) => {
  const [modal, setModal] = useState<ModalState & { data?: T }>({
    isOpen: false,
    data: initialData,
  });

  const open = useCallback((data?: T) => {
    setModal(prev => ({
      ...prev,
      isOpen: true,
      data: data || prev.data,
    }));
  }, []);

  const close = useCallback(() => {
    setModal(prev => ({
      ...prev,
      isOpen: false,
    }));
  }, []);

  const setData = useCallback((data: Partial<T>) => {
    setModal(prev => ({
      ...prev,
      data: {
        ...prev.data,
        ...data,
      } as T,
    }));
  }, []);

  const reset = useCallback(() => {
    setModal({
      isOpen: false,
      data: initialData,
    });
  }, [initialData]);

  return {
    ...modal,
    open,
    close,
    setData,
    reset,
  };
};

export default useModalState;
