import { useState, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { Pencil, Loader2, X, Check, Building2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Company, PaginatedResponse } from '@/lib/types';

interface CompanyComboboxProps {
  companyName: string | null | undefined;
  companyId: string | null | undefined;
  onSave: (companyName: string, companyId?: string) => Promise<void>;
  onNavigate?: (companyId: string) => void;
}

export function CompanyCombobox({ companyName, companyId, onSave, onNavigate }: CompanyComboboxProps) {
  const [editing, setEditing] = useState(false);
  const [search, setSearch] = useState('');
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const showDropdownRef = useRef(showDropdown);

  useEffect(() => { showDropdownRef.current = showDropdown; }, [showDropdown]);

  const { data: companies } = useQuery({
    queryKey: ['companies-search', search],
    queryFn: async () => {
      const res = await api.get<PaginatedResponse<Company>>('/companies', {
        params: { search, per_page: 10 },
      });
      return res.data.data;
    },
    enabled: editing && search.length > 0,
  });

  useEffect(() => {
    if (editing) {
      setSearch(companyName || '');
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [editing, companyName]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const doSave = async (name: string, selectedCompanyId?: string) => {
    setSaving(true);
    try {
      await onSave(name, selectedCompanyId);
      setSuccess(true);
      setEditing(false);
      setShowDropdown(false);
      setTimeout(() => setSuccess(false), 1500);
    } catch {
      // error handled by parent
    } finally {
      setSaving(false);
    }
  };

  if (editing) {
    return (
      <div className="relative" ref={dropdownRef}>
        <div className="flex items-center gap-1">
          <input
            ref={inputRef}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setShowDropdown(true);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') doSave(search);
              if (e.key === 'Escape') {
                setEditing(false);
                setShowDropdown(false);
              }
            }}
            onBlur={() => {
              // Delay to allow dropdown click; use ref to avoid stale closure
              setTimeout(() => {
                if (!showDropdownRef.current) doSave(search);
              }, 200);
            }}
            placeholder="Search or create company..."
            className="flex-1 h-7 px-2 text-sm border rounded bg-background focus:outline-none focus:ring-1 focus:ring-primary"
          />
          {saving && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
          <button onClick={() => { setEditing(false); setShowDropdown(false); }} className="text-muted-foreground hover:text-foreground">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
        {showDropdown && companies && companies.length > 0 && (
          <div className="absolute z-50 top-full left-0 w-full mt-1 bg-popover border rounded-md shadow-md max-h-48 overflow-auto">
            {companies.map((co) => (
              <button
                key={co.id}
                className="w-full text-left px-3 py-1.5 text-sm hover:bg-accent flex items-center gap-2"
                onMouseDown={(e) => {
                  e.preventDefault();
                  setShowDropdown(false);
                  doSave(co.name, co.id);
                }}
              >
                <Building2 className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                <span className="truncate">{co.name}</span>
                <span className="text-xs text-muted-foreground ml-auto">{co.contact_count} contacts</span>
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="group flex items-center gap-1 cursor-pointer min-h-[24px]" onClick={() => setEditing(true)}>
      {companyName ? (
        <span
          className={cn('truncate', companyId && 'text-primary hover:underline cursor-pointer')}
          onClick={(e) => {
            if (companyId && onNavigate) {
              e.stopPropagation();
              onNavigate(companyId);
            }
          }}
        >
          {companyName}
        </span>
      ) : (
        <span className="text-muted-foreground italic truncate">Add company...</span>
      )}
      {success && <Check className="h-3.5 w-3.5 text-green-500 shrink-0" />}
      {!success && <Pencil className="h-3 w-3 shrink-0 opacity-0 group-hover:opacity-50 transition-opacity" />}
    </div>
  );
}
