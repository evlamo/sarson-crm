import { useState, useEffect } from 'react';
import { useNavigate, useSearch } from '@tanstack/react-router';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function VerifyEmailPage() {
  useEffect(() => { document.title = 'Verify Email — Sarson Funds CRM'; }, []);
  const navigate = useNavigate();
  const search = useSearch({ from: '/verify-email' });
  const token = (search as { token?: string }).token;

  const [status, setStatus] = useState<'verifying' | 'success' | 'error'>('verifying');
  const [error, setError] = useState('');
  const [tokenExpired, setTokenExpired] = useState(false);
  const [resendLoading, setResendLoading] = useState(false);
  const [resendEmail, setResendEmail] = useState('');

  // Auto-verify on component mount
  useEffect(() => {
    if (!token) {
      setStatus('error');
      setError('No verification token provided');
      return;
    }

    api.post('/auth/verify-email', { token })
      .then((res) => {
        if (res.data.verified) {
          setStatus('success');
        } else {
          setStatus('error');
          setTokenExpired(res.data.expired);
          setError(res.data.message || 'Email verification failed');
        }
      })
      .catch((err) => {
        setStatus('error');
        const detail = err.response?.data?.detail;
        const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d: { msg?: string }) => d.msg).join(', ') : 'Email verification failed';
        setError(msg);
        if (err.response?.status === 400 && err.response?.data?.expired) {
          setTokenExpired(true);
        }
      });
  }, [token]);

  const handleResendVerification = async (e: React.FormEvent) => {
    e.preventDefault();
    setResendLoading(true);
    try {
      await api.post('/auth/resend-verification-email', { email: resendEmail });
      setStatus('verifying');
      setError('Verification email sent. Check your inbox.');
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d: { msg?: string }) => d.msg).join(', ') : 'Failed to send verification email';
      setError(msg);
    } finally {
      setResendLoading(false);
    }
  };

  // Success state
  if (status === 'success') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-secondary">
        <Card className="w-full max-w-md shadow-lg">
          <CardHeader className="text-center space-y-3">
            <div className="flex justify-center">
              <div className="w-12 h-12 rounded-lg bg-[#253a52] flex items-center justify-center text-white text-lg font-bold">SF</div>
            </div>
            <CardTitle className="text-2xl font-extrabold text-[#253a52]">Email Verified</CardTitle>
            <CardDescription className="text-sm">Your email has been confirmed</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-3 text-sm text-green-600 bg-green-50 rounded-md border border-green-200">
              Your email has been successfully verified. You can now sign in to your account.
            </div>
            <Button className="w-full" onClick={() => navigate({ to: '/login' })}>
              Go to Sign In
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Verifying state
  if (status === 'verifying') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-secondary">
        <Card className="w-full max-w-md shadow-lg">
          <CardHeader className="text-center space-y-3">
            <div className="flex justify-center">
              <div className="w-12 h-12 rounded-lg bg-[#253a52] flex items-center justify-center text-white text-lg font-bold">SF</div>
            </div>
            <CardTitle className="text-2xl font-extrabold text-[#253a52]">Verifying Email</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-center text-sm text-muted-foreground">Please wait while we verify your email…</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Error state
  return (
    <div className="min-h-screen flex items-center justify-center bg-secondary">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader className="text-center space-y-3">
          <div className="flex justify-center">
            <div className="w-12 h-12 rounded-lg bg-[#253a52] flex items-center justify-center text-white text-lg font-bold">SF</div>
          </div>
          <CardTitle className="text-2xl font-extrabold text-[#253a52]">Verification Failed</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="p-3 text-sm text-red-600 bg-red-50 rounded-md border border-red-200">
            {error || (tokenExpired ? 'This verification link has expired.' : 'Unable to verify your email.')}
          </div>

          {tokenExpired && (
            <form onSubmit={handleResendVerification} className="space-y-3">
              <div className="space-y-2">
                <label className="text-sm font-medium">Email Address</label>
                <input
                  type="email"
                  placeholder="your@email.com"
                  value={resendEmail}
                  onChange={(e) => setResendEmail(e.target.value)}
                  required
                  className="w-full px-3 py-2 border border-input rounded-md text-sm"
                />
              </div>
              <Button type="submit" className="w-full" disabled={resendLoading}>
                {resendLoading ? 'Sending…' : 'Resend Verification Email'}
              </Button>
            </form>
          )}

          <Button className="w-full" variant="outline" onClick={() => navigate({ to: '/login' })}>
            Back to Sign In
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
