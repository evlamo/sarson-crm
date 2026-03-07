import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '@/lib/api';
import { formatDate, formatTime } from '@/lib/formatDate';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { MessageSquare, Mail, Phone, Calendar, FileText, CheckCircle, Loader2 } from 'lucide-react';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export interface Activity {
  id: string;
  activity_type: 'note' | 'email' | 'call' | 'meeting' | 'task' | 'document';
  subject: string | null;
  body: string | null;
  performed_at: string;
  performed_by: string | null;
}

interface NotesSectionProps {
  contactId: string;
  className?: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const MAX_NOTE_LENGTH = 5000;

const ACTIVITY_ICONS: Record<string, typeof MessageSquare> = {
  note: MessageSquare,
  email: Mail,
  call: Phone,
  meeting: Calendar,
  task: CheckCircle,
  document: FileText,
};

// ─────────────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────────────

export function NotesSection({ contactId, className }: NotesSectionProps) {
  const queryClient = useQueryClient();
  const [noteText, setNoteText] = useState('');
  const [focusOnAdd, setFocusOnAdd] = useState(false);

  // ─── Queries ───
  const {
    data: activities = [],
    isLoading,
    isError,
    error,
  } = useQuery<Activity[]>({
    queryKey: ['contact-activities', contactId],
    queryFn: async () => {
      const res = await api.get<{ data: Activity[] }>(`/contacts/${contactId}/activities`);
      return res.data.data || [];
    },
  });

  // ─── Mutations with Optimistic Updates ───
  const addNoteMutation = useMutation({
    mutationFn: async (body: string) => {
      const response = await api.post<{ data: Activity }>(`/contacts/${contactId}/activities`, {
        activity_type: 'note',
        body,
      });
      return response.data.data;
    },
    onMutate: async (newNoteBody: string) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['contact-activities', contactId] });

      // Snapshot previous value
      const previousActivities = queryClient.getQueryData<Activity[]>(['contact-activities', contactId]);

      // Optimistically update
      const optimisticNote: Activity = {
        id: `temp-${Date.now()}`,
        activity_type: 'note',
        subject: null,
        body: newNoteBody,
        performed_at: new Date().toISOString(),
        performed_by: null,
      };

      queryClient.setQueryData<Activity[]>(['contact-activities', contactId], (old = []) => [
        optimisticNote,
        ...old,
      ]);

      setNoteText('');
      return { previousActivities };
    },
    onError: (err, _variables, context) => {
      // Rollback on error
      if (context?.previousActivities) {
        queryClient.setQueryData(['contact-activities', contactId], context.previousActivities);
      }
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail || 'Failed to add note');
    },
    onSuccess: () => {
      // Refetch to get server data (including proper ID, timestamps, etc.)
      queryClient.invalidateQueries({ queryKey: ['contact-activities', contactId] });
      toast.success('Note added');
      setFocusOnAdd(false);
    },
  });

  // ─── Handlers ───
  const handleAddNote = () => {
    const trimmed = noteText.trim();
    if (!trimmed) return;
    if (trimmed.length > MAX_NOTE_LENGTH) {
      toast.error(`Note exceeds ${MAX_NOTE_LENGTH} character limit`);
      return;
    }
    addNoteMutation.mutate(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Ctrl/Cmd + Enter to submit
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleAddNote();
    }
  };

  const remainingChars = MAX_NOTE_LENGTH - noteText.length;
  const isOverLimit = remainingChars < 0;

  // ─── Render ───
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-widest">
          Notes & Activity
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col">
        {/* ─── Add Note Form ─── */}
        <div className="space-y-2 mb-4">
          <div className="relative">
            <Textarea
              placeholder="Write a note... (Ctrl+Enter to save)"
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => setFocusOnAdd(true)}
              maxLength={MAX_NOTE_LENGTH}
              rows={focusOnAdd ? 4 : 2}
              aria-label="Add a new note"
              aria-describedby="note-char-count"
              className={`resize-none transition-all ${isOverLimit ? 'border-red-500 focus-visible:ring-red-500' : ''}`}
            />
          </div>
          <div className="flex items-center justify-between gap-2">
            <span
              id="note-char-count"
              className={`text-xs transition-colors ${
                remainingChars < 100 ? (isOverLimit ? 'text-red-500' : 'text-orange-500') : 'text-muted-foreground'
              }`}
              aria-live="polite"
            >
              {remainingChars.toLocaleString()} characters remaining
            </span>
            <Button
              size="sm"
              disabled={!noteText.trim() || isOverLimit || addNoteMutation.isPending}
              onClick={handleAddNote}
              className="min-w-[80px]"
            >
              {addNoteMutation.isPending ? (
                <>
                  <Loader2 className="h-3 w-3 mr-1.5 animate-spin" />
                  Saving...
                </>
              ) : (
                'Add Note'
              )}
            </Button>
          </div>
        </div>

        <Separator />

        {/* ─── Activities List ─── */}
        <div
          className="space-y-3 mt-4 flex-1 overflow-y-auto max-h-[600px]"
          role="feed"
          aria-label="Activity feed"
          aria-busy={isLoading}
        >
          {/* Loading State */}
          {isLoading && (
            <div className="space-y-3" role="status" aria-label="Loading activities">
              {[1, 2, 3].map((i) => (
                <div key={i} className="flex gap-3 animate-pulse">
                  <div className="h-7 w-7 rounded-full bg-muted shrink-0" />
                  <div className="flex-1 space-y-2">
                    <div className="h-3 bg-muted rounded w-1/3" />
                    <div className="h-4 bg-muted rounded w-2/3" />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Error State */}
          {isError && (
            <div className="text-center py-8" role="alert">
              <MessageSquare className="h-8 w-8 mx-auto text-red-500/40 mb-2" />
              <p className="text-sm text-red-600 font-medium">Failed to load activities</p>
              <p className="text-xs text-muted-foreground mt-1">
                {(error as Error)?.message || 'Something went wrong'}
              </p>
              <Button
                size="sm"
                variant="outline"
                className="mt-4"
                onClick={() => queryClient.invalidateQueries({ queryKey: ['contact-activities', contactId] })}
              >
                Retry
              </Button>
            </div>
          )}

          {/* Empty State */}
          {!isLoading && !isError && activities.length === 0 && (
            <div className="text-center py-8">
              <MessageSquare className="h-8 w-8 mx-auto text-muted-foreground/40 mb-2" />
              <p className="text-sm text-muted-foreground">No notes yet</p>
              <p className="text-xs text-muted-foreground mt-1">Add a note to start tracking progress</p>
            </div>
          )}

          {/* Activities List */}
          {!isLoading &&
            !isError &&
            activities.length > 0 &&
            activities.map((activity) => {
              const Icon = ACTIVITY_ICONS[activity.activity_type] || FileText;
              const isNote = activity.activity_type === 'note';
              const dateStr = activity.performed_at ? formatDate(activity.performed_at) : '';
              const timeStr = activity.performed_at ? formatTime(activity.performed_at) : '';
              const isOptimistic = activity.id.startsWith('temp-');

              return (
                <article
                  key={activity.id}
                  className={`flex gap-3 group ${isOptimistic ? 'opacity-60' : ''}`}
                  role="article"
                  aria-label={`${activity.activity_type} from ${dateStr} at ${timeStr}`}
                >
                  <div
                    className={`mt-1 shrink-0 h-7 w-7 rounded-full flex items-center justify-center transition-colors ${
                      isNote ? 'bg-primary/10' : 'bg-muted'
                    }`}
                    aria-hidden="true"
                  >
                    <Icon className={`h-3.5 w-3.5 ${isNote ? 'text-primary' : 'text-muted-foreground'}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline gap-2 flex-wrap">
                      {!isNote && (
                        <span className="text-xs font-semibold capitalize text-muted-foreground">
                          {activity.activity_type}
                        </span>
                      )}
                      <time className="text-xs text-muted-foreground" dateTime={activity.performed_at}>
                        {dateStr}
                      </time>
                      <span className="text-xs text-muted-foreground/60">{timeStr}</span>
                      {isOptimistic && (
                        <span className="text-xs text-muted-foreground/60 italic">Saving...</span>
                      )}
                    </div>
                    {activity.subject && <p className="text-sm font-medium mt-0.5">{activity.subject}</p>}
                    {activity.body && (
                      <p className="text-sm mt-0.5 whitespace-pre-wrap leading-relaxed break-words">
                        {activity.body}
                      </p>
                    )}
                  </div>
                </article>
              );
            })}
        </div>
      </CardContent>
    </Card>
  );
}
