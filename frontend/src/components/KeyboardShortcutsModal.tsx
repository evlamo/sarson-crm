import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

interface KeyboardShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface Shortcut {
  keys: string[];
  description: string;
}

const shortcuts: { category: string; items: Shortcut[] }[] = [
  {
    category: 'Navigation',
    items: [
      { keys: ['G', 'C'], description: 'Go to Contacts' },
      { keys: ['G', 'L'], description: 'Go to Lists' },
      { keys: ['G', 'A'], description: 'Go to Activity' },
      { keys: ['G', 'O'], description: 'Go to Companies' },
      { keys: ['G', 'S'], description: 'Go to Sales Campaigns' },
    ],
  },
  {
    category: 'Actions',
    items: [
      { keys: ['N'], description: 'New contact' },
      { keys: ['/'], description: 'Focus search' },
      { keys: ['Esc'], description: 'Close modal / Clear search' },
    ],
  },
  {
    category: 'Help',
    items: [
      { keys: ['?'], description: 'Toggle help panel' },
      { keys: ['Shift', '?'], description: 'Show keyboard shortcuts' },
    ],
  },
];

export default function KeyboardShortcutsModal({
  isOpen,
  onClose,
}: KeyboardShortcutsModalProps) {
  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Keyboard Shortcuts</DialogTitle>
        </DialogHeader>
        <div className="space-y-6 py-2">
          {shortcuts.map((section) => (
            <div key={section.category}>
              <h3 className="text-sm font-semibold text-muted-foreground mb-3">
                {section.category}
              </h3>
              <div className="space-y-2">
                {section.items.map((shortcut, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between py-1"
                  >
                    <span className="text-sm text-foreground">
                      {shortcut.description}
                    </span>
                    <div className="flex items-center gap-1">
                      {shortcut.keys.map((key, keyIdx) => (
                        <span key={keyIdx}>
                          <kbd className="px-2 py-1 text-xs font-mono bg-muted border rounded-md shadow-sm">
                            {key}
                          </kbd>
                          {keyIdx < shortcut.keys.length - 1 && (
                            <span className="text-muted-foreground mx-0.5">+</span>
                          )}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
        <div className="pt-2 border-t">
          <p className="text-xs text-muted-foreground text-center">
            Press <kbd className="px-1.5 py-0.5 bg-muted rounded text-xs">Esc</kbd> to close
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
