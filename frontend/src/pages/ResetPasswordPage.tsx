import { useState, useEffect } from 'react';
import { useNavigate, useSearch } from '@tanstack/react-router';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function ResetPasswordPage() {
  useEffect(() => { document.title = 'Create New Password — Sarson Funds CRM'; }, []);
  const navigate = useNavigate();
  const search = useSearch({ from: '/reset-password' });
  const token = (search as { token?: string }).token;
  
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [tokenValidated, setTokenValidated] = useState<boolean | null>(null);
  const [tokenExpired, setTokenExpired] = useState(false);

  // Validate token on mount
  useEffect(() => {
    if (!token) {
      setTokenValidated(false);
      return;
    }
    
    api.post('/auth/validate-reset-token', { token })
      .then((res) => {
        if (res.data.valid) {
          setTokenValidated(true);
        } else {
          setTokenValidated(false);
          setTokenExpired(res.data.expired);
        }
      })
      .catch(() => setTokenValidated(false));
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Validate passwords match
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    // Validate password strength
    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    setLoading(true);
    try {
      await api.post('/auth/reset-password', { token, new_password: password });
      setSuccess(true);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d: { msg?: string }) => d.msg).join(', ') : 'Failed to reset password';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  // Invalid or expired token
  if (tokenValidated === false) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-secondary">
        <Card className="w-full max-w-md shadow-lg">
          <CardHeader className="text-center space-y-3">
            <div className="flex justify-center">
              <div className="w-12 h-12 rounded-lg bg-[#253a52] flex items-center justify-center text-white text-lg font-bold">SF</div>
            </div>
            <CardTitle className="text-2xl font-extrabold text-[#253a52]">Sarson Funds CRM</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="p-3 text-sm text-red-600 bg-red-50 rounded-md border border-red-200">
              {tokenExpired
                ? 'This password reset link has expired. Request a new one.'
                : 'This password reset link is invalid. Request a new one.'}
            </div>
            <Button className="w-full mt-4" onClick={() => navigate({ to: '/forgot-password' })}>
              Request New Link
            </Button>
            <Button className="w-full mt-2" variant="outline" onClick={() => navigate({ to: '/login' })}>
              Back to Sign In
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Success state
  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-secondary">
        <Card className="w-full max-w-md shadow-lg">
          <CardHeader className="text-center space-y-3">
            <div className="flex justify-center">
              <div className="w-12 h-12 rounded-lg bg-[#253a52] flex items-center justify-center text-white text-lg font-bold">SF</div>
            </div>
            <CardTitle className="text-2xl font-extrabold text-[#253a52]">Password Reset</CardTitle>
            <CardDescription className="text-sm">Your password has been updated</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="p-3 text-sm text-green-600 bg-green-50 rounded-md border border-green-200 mb-4">
              Your password has been successfully reset. You can now sign in with your new password.
            </div>
            <Button className="w-full" onClick={() => navigate({ to: '/login' })}>
              Back to Sign In
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Loading token validation
  if (tokenValidated === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-secondary">
        <Card className="w-full max-w-md shadow-lg">
          <CardHeader className="text-center space-y-3">
            <div className="flex justify-center">
              <div className="w-12 h-12 rounded-lg bg-[#253a52] flex items-center justify-center text-white text-lg font-bold">SF</div>
            </div>
            <CardTitle className="text-2xl font-extrabold text-[#253a52]">Sarson Funds CRM</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-center text-sm text-muted-foreground">Validating reset link…</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-secondary">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader className="text-center space-y-3">
          <div className="flex justify-center">
            <div className="w-12 h-12 rounded-lg bg-[#253a52] flex items-center justify-center text-white text-lg font-bold">SF</div>
          </div>
          <CardTitle className="text-2xl font-extrabold text-[#253a52]">Create New Password</CardTitle>
          <CardDescription className="text-sm">Enter your new password below</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 text-sm text-red-600 bg-red-50 rounded-md border border-red-200">
                {error}
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="password">New Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="8+ characters, 1 uppercase, 1 number"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirm Password</Label>
              <Input
                id="confirmPassword"
                type="password"
                placeholder="Confirm your password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={8}
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Resetting…' : 'Reset Password'}
            </Button>
          </form>

          <p className="mt-5 text-center text-sm text-muted-foreground">
            <a
              href="/login"
              className="text-[#253a52] font-medium hover:underline"
              onClick={(e) => { e.preventDefault(); navigate({ to: '/login' }); }}
            >
              Back to Sign In
            </a>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
