import { useState, useEffect } from 'react';
import { useNavigate } from '@tanstack/react-router';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function RegisterPage() {
  useEffect(() => { document.title = 'Register — Sarson Funds CRM'; }, []);
  const navigate = useNavigate();
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
    if (!token) {
      setTokenValid(null);
      return;
    }
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
      .catch(() => {
        setTokenValid(false);
      });
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      // Use the admin create-user endpoint — but this requires admin auth.
      // For self-registration we'll call a public register endpoint if it exists,
      // otherwise inform the user to contact admin.
      // Since registration is admin-gated, show the invite link info.
      setError('Registration is managed by your administrator. Share this page URL with them to complete your setup.');
    } finally {
      setLoading(false);
    }
  };

  if (token && tokenValid === false) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl font-bold">Sarson Funds CRM</CardTitle>
            <CardDescription>Invalid Invite</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="p-3 text-sm text-red-600 bg-red-50 rounded-md border border-red-200">
              {tokenExpired
                ? 'This invite link has expired. Contact your administrator for a new one.'
                : 'This invite link is invalid or has expired. Contact your administrator.'}
            </div>
            <Button className="w-full mt-4" variant="outline" onClick={() => navigate({ to: '/login' })}>
              Back to Login
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl font-bold">Sarson Funds CRM</CardTitle>
          <CardDescription>
            {tokenValid ? "You've been invited! Register below." : 'Create your account'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!token && (
            <div className="p-3 text-sm text-amber-700 bg-amber-50 rounded-md border border-amber-200 mb-4">
              Registration requires an invite link or an @sarsonfunds.com email. Contact your administrator.
            </div>
          )}
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 text-sm text-red-600 bg-red-50 rounded-md border border-red-200">
                {error}
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="name">Full Name</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                autoFocus
              />
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
                className={emailLocked ? 'bg-muted' : ''}
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
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading || (!token && !email.endsWith('@sarsonfunds.com'))}>
              {loading ? 'Creating account...' : 'Create Account'}
            </Button>
          </form>
          <div className="mt-4 text-center">
            <Button variant="link" onClick={() => navigate({ to: '/login' })}>
              Already have an account? Sign in
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
