import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/hooks/useAuth';
import api from '@/lib/api';
import { formatDate } from '@/lib/formatDate';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { toast } from 'sonner';

interface Invite {
  id: string;
  email: string;
  status: string;
  invited_by: string;
  invited_by_name: string | null;
  created_at: string;
  expires_at: string;
  accepted_at: string | null;
  token?: string;
  invite_url?: string;
}

function statusBadge(status: string, expiresAt: string) {
  const isExpired = status === 'pending' && new Date(expiresAt) < new Date();
  const displayStatus = isExpired ? 'expired' : status;

  const variants: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-800 border-yellow-300',
    accepted: 'bg-green-100 text-green-800 border-green-300',
    revoked: 'bg-gray-100 text-gray-600 border-gray-300',
    expired: 'bg-red-100 text-red-800 border-red-300',
  };

  return (
    <Badge variant="outline" className={variants[displayStatus] || ''}>
      {displayStatus.charAt(0).toUpperCase() + displayStatus.slice(1)}
    </Badge>
  );
}

export default function InvitesPage() {
  useEffect(() => { document.title = 'Team & Invites — Sarson Funds CRM'; }, []);
  const isAdmin = useAuth((s) => s.isAdmin);
  const queryClient = useQueryClient();
  const [email, setEmail] = useState('');
  const [lastInviteUrl, setLastInviteUrl] = useState('');

  const { data: invites = [], isLoading } = useQuery<Invite[]>({
    queryKey: ['invites'],
    queryFn: async () => {
      const res = await api.get('/invites/');
      return res.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (inviteEmail: string) => {
      const res = await api.post('/invites/', { email: inviteEmail });
      return res.data as Invite;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['invites'] });
      setLastInviteUrl(data.invite_url || '');
      setEmail('');
      toast.success(`Invite sent to ${data.email}`);
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail || 'Failed to create invite';
      toast.error(detail);
    },
  });

  const revokeMutation = useMutation({
    mutationFn: async (inviteId: string) => {
      await api.delete(`/invites/${inviteId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invites'] });
      toast.success('Invite revoked');
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail || 'Failed to revoke invite';
      toast.error(detail);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    createMutation.mutate(email.trim());
  };

  const handleRevoke = (inviteId: string) => {
    if (!confirm('Revoke this invite? The link will no longer work.')) return;
    revokeMutation.mutate(inviteId);
  };

  const copyUrl = (url: string) => {
    navigator.clipboard.writeText(url);
    toast.success('Invite link copied!');
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Team & Invites</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {isAdmin ? "Viewing all team invites." : "You can invite team members. You'll only see invites you created."}
        </p>
      </div>

      {/* Create invite */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Invite a Team Member</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex items-end gap-3">
            <div className="flex-1 space-y-2">
              <Label htmlFor="invite-email">Email Address</Label>
              <Input
                id="invite-email"
                type="email"
                placeholder="teammate@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? 'Sending...' : 'Send Invite'}
            </Button>
          </form>
          {lastInviteUrl && (
            <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-md">
              <p className="text-sm text-green-800 font-medium mb-1">Invite link created:</p>
              <div className="flex items-center gap-2">
                <code className="text-xs bg-white px-2 py-1 rounded border flex-1 truncate">
                  {lastInviteUrl}
                </code>
                <Button size="sm" variant="outline" onClick={() => copyUrl(lastInviteUrl)}>
                  Copy
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Invites table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">All Invites</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-muted-foreground text-sm">Loading...</p>
          ) : invites.length === 0 ? (
            <p className="text-muted-foreground text-sm">No invites yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Email</TableHead>
                  <TableHead>Invited By</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Expires</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invites.map((inv) => {
                  const isPending = inv.status === 'pending' && new Date(inv.expires_at) > new Date();
                  return (
                    <TableRow key={inv.id}>
                      <TableCell className="font-medium">{inv.email}</TableCell>
                      <TableCell>{inv.invited_by_name || '—'}</TableCell>
                      <TableCell>{statusBadge(inv.status, inv.expires_at)}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDate(inv.created_at)}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDate(inv.expires_at)}
                      </TableCell>
                      <TableCell>
                        {isPending && (
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => handleRevoke(inv.id)}
                            disabled={revokeMutation.isPending}
                          >
                            Revoke
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
