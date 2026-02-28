import { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Trash2, Tag } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';

interface TagWithCount {
  id: string;
  name: string;
  color: string | null;
  contact_count: number;
}

export default function TagsPage() {
  const queryClient = useQueryClient();
  const [newTagName, setNewTagName] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<TagWithCount | null>(null);
  const editRef = useRef<HTMLInputElement>(null);

  useEffect(() => { document.title = 'Tags — Sarson Funds CRM'; }, []);

  const { data: tags = [], isLoading } = useQuery<TagWithCount[]>({
    queryKey: ['tags', 'with-counts'],
    queryFn: async () => {
      const res = await api.get('/tags', { params: { with_counts: true } });
      return res.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (name: string) => {
      await api.post('/tags', { name });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tags'] });
      setNewTagName('');
    },
  });

  const renameMutation = useMutation({
    mutationFn: async ({ id, name }: { id: string; name: string }) => {
      await api.patch(`/tags/${id}`, { name });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tags'] });
      setEditingId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/tags/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tags'] });
      setDeleteTarget(null);
    },
  });

  const startEdit = (tag: TagWithCount) => {
    setEditingId(tag.id);
    setEditDraft(tag.name);
    setTimeout(() => editRef.current?.focus(), 0);
  };

  const saveEdit = (id: string) => {
    const trimmed = editDraft.trim();
    if (trimmed && trimmed !== tags.find(t => t.id === id)?.name) {
      renameMutation.mutate({ id, name: trimmed });
    } else {
      setEditingId(null);
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold">Tags</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Manage contact tags</p>
      </div>

      {/* Create new tag */}
      <Card>
        <CardContent className="pt-6">
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (newTagName.trim()) createMutation.mutate(newTagName.trim());
            }}
          >
            <Input
              value={newTagName}
              onChange={(e) => setNewTagName(e.target.value)}
              placeholder="New tag name..."
              className="flex-1"
            />
            <Button type="submit" disabled={!newTagName.trim() || createMutation.isPending}>
              Create
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Tags list */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Tag className="h-4 w-4" />
            All Tags ({tags.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-10 bg-muted rounded animate-pulse" />
              ))}
            </div>
          ) : tags.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">No tags yet. Create one above.</p>
          ) : (
            <div className="divide-y">
              {tags.map((tag) => (
                <div key={tag.id} className="flex items-center justify-between py-3 group">
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <span
                      className="w-3 h-3 rounded-full shrink-0"
                      style={{ backgroundColor: tag.color || '#6b7280' }}
                    />
                    {editingId === tag.id ? (
                      <input
                        ref={editRef}
                        value={editDraft}
                        onChange={(e) => setEditDraft(e.target.value)}
                        onBlur={() => saveEdit(tag.id)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') saveEdit(tag.id);
                          if (e.key === 'Escape') setEditingId(null);
                        }}
                        className="flex-1 h-7 px-2 text-sm border rounded bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                      />
                    ) : (
                      <span
                        className="text-sm font-medium cursor-pointer hover:underline"
                        onClick={() => startEdit(tag)}
                      >
                        {tag.name}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-muted-foreground">
                      {tag.contact_count} contact{tag.contact_count !== 1 ? 's' : ''}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive"
                      onClick={() => setDeleteTarget(tag)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete confirmation */}
      <Dialog open={!!deleteTarget} onOpenChange={(v) => !v && setDeleteTarget(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-destructive">Delete tag "{deleteTarget?.name}"?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            This will remove the tag from {deleteTarget?.contact_count || 0} contact{deleteTarget?.contact_count !== 1 ? 's' : ''}. This cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button
              variant="destructive"
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
