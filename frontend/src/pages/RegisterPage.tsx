import { useState, useEffect } from 'react';
import { useNavigate } from '@tanstack/react-router';
import api from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function RegisterPage() {
  useEffect(() => { document.title = 'Create Account — Sarson Funds CRM'; }, []);
  const navigate = useNavigate();
  const login = useAuth((s) => s.login);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [tokenValid, setTokenValid] = useState<boolean | null>(null);
  const [tokenExpired, setTokenExpired] = useState(false);
  const [emailLocked, setEmailLocked] = useState(false);

  const params = new URLSearchParams(window.location.search);
  const token = params.get('token');

  useEffect(() => {
    if (!token) return;
    api.get(`/invites/validate/${token}`)
      .then((res) => {
        if (res.data.valid) {
          setTokenValid(true);
          setEmail(res.data.email);
          setEmailLocked(true);
        } else {
          setTokenValid(false);
          setTokenExpired(res.data.expired);
        }
      })
      .catch(() => setTokenValid(false));
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await api.post('/auth/register', { name, email, password, invite_token: token ?? undefined });
      try {
        await login(email, password);
        navigate({ to: '/' });
      } catch {
        // Registered successfully but auto-login failed — redirect to login
        navigate({ to: '/login' });
      }
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail
        : Array.isArray(detail) ? detail.map((d: { msg?: string }) => d.msg).join(', ')
        : 'Registration failed. Please try again.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  if (token && tokenValid === false) {
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
                ? 'This invite link has expired. Contact your administrator for a new one.'
                : 'This invite link is invalid. Contact your administrator.'}
            </div>
            <Button className="w-full mt-4" variant="outline" onClick={() => navigate({ to: '/login' })}>
              Back to Sign In
            </Button>
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
          <CardTitle className="text-2xl font-extrabold text-[#253a52]">Sarson Funds CRM</CardTitle>
          <CardDescription className="text-sm">
            {tokenValid ? "You've been invited — set up your account below." : 'Internal Operations Platform'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 text-sm text-red-600 bg-red-50 rounded-md border border-red-200">{error}</div>
            )}
            <div className="space-y-2">
              <Label htmlFor="name">Full Name</Label>
              <Input id="name" value={name} onChange={(e) => setName(e.target.value)} required autoFocus placeholder="Jane Smith" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                readOnly={emailLocked}
                className={emailLocked ? 'bg-muted cursor-not-allowed' : ''}
                placeholder="you@sarsonfunds.com"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                placeholder="8+ characters, 1 uppercase, 1 number"
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Creating account…' : 'Create Account'}
            </Button>
          </form>

          {/* Small sign-in link — standard pattern */}
          <p className="mt-5 text-center text-sm text-muted-foreground">
            Already have an account?{' '}
            <a
              href="/login"
              className="text-[#253a52] font-medium hover:underline"
              onClick={(e) => { e.preventDefault(); navigate({ to: '/login' }); }}
            >
              Sign in
            </a>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
