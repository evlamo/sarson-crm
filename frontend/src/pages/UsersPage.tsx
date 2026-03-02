import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
import { formatDate } from '@/lib/formatDate';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { AlertCircle } from 'lucide-react';

interface UserRow {
  id: string;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  last_login: string | null;
  created_at: string;
}

export default function UsersPage() {
  const currentUser = useAuth((s) => s.user);
  const isAdmin = useAuth((s) => s.isAdmin);
  const queryClient = useQueryClient();
  const [resetTarget, setResetTarget] = useState<UserRow | null>(null);
  const [newPassword, setNewPassword] = useState('');
  const [confirmDeactivate, setConfirmDeactivate] = useState<UserRow | null>(null);

  useEffect(() => { document.title = 'Users — Sarson Funds CRM'; }, []);

  // Admin check — hide page content if not admin
  if (!isAdmin) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-muted-foreground">
        <AlertCircle className="h-12 w-12 mb-4 text-destructive" />
        <p className="text-lg font-semibold">Access Denied</p>
        <p className="text-sm mt-1">You don't have permission to view this page.</p>
      </div>
    );
  }

  const { data: users = [], isLoading } = useQuery<UserRow[]>({
    queryKey: ['users'],
    queryFn: async () => {
      const res = await api.get('/users/');
      return res.data;
    },
    enabled: isAdmin,
  });

  const deactivate = useMutation({
    mutationFn: async (userId: string) => {
      await api.patch(`/users/${userId}/deactivate`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      toast.success('User deactivated');
      setConfirmDeactivate(null);
    },
    onError: () => toast.error('Failed to deactivate user'),
  });

  const resetPassword = useMutation({
    mutationFn: async ({ userId, password }: { userId: string; password: string }) => {
      await api.post(`/users/${userId}/reset-password`, { new_password: password });
    },
    onSuccess: () => {
      toast.success('Password reset');
      setResetTarget(null);
      setNewPassword('');
    },
    onError: () => toast.error('Failed to reset password'),
  });

  const getRoleBadge = (role: string) => {
    switch (role) {
      case 'owner':
        return <Badge className="bg-purple-600">Owner</Badge>;
      case 'admin':
        return <Badge className="bg-blue-600">Admin</Badge>;
      default:
        return <Badge variant="secondary">Member</Badge>;
    }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">User Management</h1>

      {isLoading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : (
        <div className="space-y-2">
          {users.map((u) => {
            const isMe = u.id === currentUser?.id;
            return (
              <Card key={u.id}>
                <CardContent className="flex items-center justify-between py-3">
                  <div className="flex items-center gap-3">
                    <div>
                      <span className="font-medium">{u.name}</span>
                      {isMe && <span className="text-xs text-muted-foreground ml-1">(You)</span>}
                      <p className="text-sm text-muted-foreground">{u.email}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {getRoleBadge(u.role)}
                    {!u.is_active && <Badge variant="destructive">Inactive</Badge>}
                    <span className="text-xs text-muted-foreground">
                      {u.last_login ? `Last login: ${formatDate(u.last_login)}` : 'Never logged in'}
                    </span>
                    <Button size="sm" variant="outline" onClick={() => setResetTarget(u)}>
                      Reset Password
                    </Button>
                    {!isMe && u.is_active && (
                      <Button size="sm" variant="destructive" onClick={() => setConfirmDeactivate(u)}>
                        Deactivate
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Reset Password Modal */}
      <Dialog open={!!resetTarget} onOpenChange={() => { setResetTarget(null); setNewPassword(''); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reset Password for {resetTarget?.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>New Password</Label>
              <Input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
            </div>
            <Button
              disabled={!newPassword || resetPassword.isPending}
              onClick={() => resetTarget && resetPassword.mutate({ userId: resetTarget.id, password: newPassword })}
            >
              {resetPassword.isPending ? 'Resetting...' : 'Reset Password'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Deactivate Confirmation */}
      <Dialog open={!!confirmDeactivate} onOpenChange={() => setConfirmDeactivate(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Deactivate {confirmDeactivate?.name}?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            This will prevent {confirmDeactivate?.email} from logging in. This action can be reversed.
          </p>
          <div className="flex gap-2 justify-end">
            <Button variant="outline" onClick={() => setConfirmDeactivate(null)}>Cancel</Button>
            <Button
              variant="destructive"
              disabled={deactivate.isPending}
              onClick={() => confirmDeactivate && deactivate.mutate(confirmDeactivate.id)}
            >
              {deactivate.isPending ? 'Deactivating...' : 'Deactivate'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
