import { useState, useEffect } from 'react';
import { useNavigate } from '@tanstack/react-router';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function ForgotPasswordPage() {
  useEffect(() => { document.title = 'Reset Password — Sarson Funds CRM'; }, []);
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await api.post('/auth/forgot-password', { email });
      setSubmitted(true);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d: { msg?: string }) => d.msg).join(', ') : 'Failed to send reset email';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-secondary">
        <Card className="w-full max-w-md shadow-lg">
          <CardHeader className="text-center space-y-3">
            <div className="flex justify-center">
              <div className="w-12 h-12 rounded-lg bg-[#253a52] flex items-center justify-center text-white text-lg font-bold">SF</div>
            </div>
            <CardTitle className="text-2xl font-extrabold text-[#253a52]">Check Your Email</CardTitle>
            <CardDescription className="text-sm">We've sent a password reset link</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-3 text-sm text-green-600 bg-green-50 rounded-md border border-green-200">
              Check your inbox for a password reset link. The link expires in 24 hours.
            </div>
            <p className="text-sm text-muted-foreground">
              Can't find the email? Check your spam folder or <a href="#" className="text-[#253a52] font-medium hover:underline" onClick={(e) => { e.preventDefault(); setSubmitted(false); setEmail(''); }}>try again</a>.
            </p>
            <Button className="w-full" variant="outline" onClick={() => navigate({ to: '/login' })}>
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
          <CardTitle className="text-2xl font-extrabold text-[#253a52]">Reset Password</CardTitle>
          <CardDescription className="text-sm">Enter your email to receive a reset link</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 text-sm text-red-600 bg-red-50 rounded-md border border-red-200">
                {error}
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@sarsonfunds.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Sending…' : 'Send Reset Link'}
            </Button>
          </form>

          <p className="mt-5 text-center text-sm text-muted-foreground">
            Remember your password?{' '}
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
