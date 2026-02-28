import { useState, useRef, useEffect } from 'react';
import { Pencil, Check, Loader2, X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface EditableFieldProps {
  value: string | null | undefined;
  type?: 'text' | 'email' | 'tel' | 'url' | 'select' | 'textarea';
  options?: { value: string; label: string }[];
  onSave: (value: string) => Promise<void>;
  placeholder?: string;
  label?: string;
  hint?: string;
  /** Render the display value as a link */
  linkHref?: string;
  /** Render custom display instead of plain text */
  renderDisplay?: (value: string | null | undefined) => React.ReactNode;
  className?: string;
}

export function EditableField({
  value,
  type = 'text',
  options = [],
  onSave,
  placeholder = '—',
  label,
  hint,
  linkHref,
  renderDisplay,
  className,
}: EditableFieldProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value || '');
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState(false);
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>(null);

  useEffect(() => {
    if (editing) {
      setDraft(value || '');
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [editing, value]);

  const save = async () => {
    if (draft === (value || '')) {
      setEditing(false);
      return;
    }
    // Email validation
    if (type === 'email' && draft && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(draft)) {
      setError(true);
      setTimeout(() => setError(false), 2000);
      return;
    }
    setSaving(true);
    setError(false);
    try {
      await onSave(draft);
      setSuccess(true);
      setEditing(false);
      setTimeout(() => setSuccess(false), 1500);
    } catch {
      setError(true);
      setTimeout(() => setError(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  const cancel = () => {
    setDraft(value || '');
    setEditing(false);
    setError(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && type !== 'textarea') save();
    if (e.key === 'Enter' && type === 'textarea' && (e.metaKey || e.ctrlKey)) save();
    if (e.key === 'Escape') cancel();
  };

  if (editing) {
    return (
      <div className={cn('flex items-center gap-1', className)}>
        {type === 'select' ? (
          <select
            ref={inputRef as React.RefObject<HTMLSelectElement>}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={save}
            onKeyDown={handleKeyDown}
            className={cn(
              'flex-1 h-7 px-2 text-sm border rounded bg-background focus:outline-none focus:ring-1 focus:ring-primary',
              error && 'border-red-500 ring-red-500'
            )}
          >
            <option value="">—</option>
            {options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        ) : type === 'textarea' ? (
          <textarea
            ref={inputRef as React.RefObject<HTMLTextAreaElement>}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={save}
            onKeyDown={handleKeyDown}
            rows={3}
            className={cn(
              'flex-1 px-2 py-1 text-sm border rounded bg-background focus:outline-none focus:ring-1 focus:ring-primary resize-none',
              error && 'border-red-500 ring-red-500'
            )}
            placeholder={placeholder}
          />
        ) : (
          <input
            ref={inputRef as React.RefObject<HTMLInputElement>}
            type={type}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={save}
            onKeyDown={handleKeyDown}
            placeholder={hint || placeholder}
            className={cn(
              'flex-1 h-7 px-2 text-sm border rounded bg-background focus:outline-none focus:ring-1 focus:ring-primary',
              error && 'border-red-500 ring-red-500'
            )}
          />
        )}
        {saving && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground shrink-0" />}
        <button onClick={cancel} className="text-muted-foreground hover:text-foreground shrink-0">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    );
  }

  const displayValue = value || '';
  const isEmpty = !displayValue;

  return (
    <div
      className={cn('group flex items-center gap-1 cursor-pointer min-h-[24px]', className)}
      onClick={() => setEditing(true)}
    >
      {renderDisplay ? (
        renderDisplay(value)
      ) : linkHref && displayValue ? (
        <a
          href={linkHref}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline truncate"
          onClick={(e) => e.stopPropagation()}
        >
          {displayValue}
        </a>
      ) : (
        <span className={cn('truncate', isEmpty && 'text-muted-foreground italic')}>
          {displayValue || placeholder}
        </span>
      )}
      {success && <Check className="h-3.5 w-3.5 text-green-500 shrink-0" />}
      {!success && (
        <Pencil className="h-3 w-3 shrink-0 opacity-0 group-hover:opacity-50 transition-opacity" />
      )}
    </div>
  );
}
