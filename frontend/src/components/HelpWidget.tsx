import { useState, useEffect, useCallback } from 'react';
import { HelpCircle } from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetTitle,
} from '@/components/ui/sheet';
import HelpPanel from './HelpPanel';

interface HelpWidgetProps {
  isOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
}

export default function HelpWidget({ isOpen: controlledOpen, onOpenChange }: HelpWidgetProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  
  // Support both controlled and uncontrolled modes
  const isOpen = controlledOpen !== undefined ? controlledOpen : internalOpen;
  const setIsOpen = useCallback((open: boolean) => {
    if (onOpenChange) {
      onOpenChange(open);
    }
    setInternalOpen(open);
  }, [onOpenChange]);

  // Global keyboard handler for ? key (handled in Layout.tsx)
  // This component just renders the UI

  return (
    <>
      {/* Floating Button */}
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-40 w-12 h-12 rounded-full bg-[#253a52] text-white shadow-lg hover:bg-[#1e3045] transition-colors flex items-center justify-center group"
        aria-label="Open help"
      >
        <HelpCircle className="h-6 w-6 group-hover:scale-110 transition-transform" />
      </button>

      {/* Slide-in Panel */}
      <Sheet open={isOpen} onOpenChange={setIsOpen}>
        <SheetContent 
          side="right" 
          className="w-full sm:w-[380px] p-0"
          showCloseButton={true}
        >
          <SheetTitle className="sr-only">Help Center</SheetTitle>
          <HelpPanel onClose={() => setIsOpen(false)} />
        </SheetContent>
      </Sheet>
    </>
  );
}
