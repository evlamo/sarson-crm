import { useState, useEffect } from 'react';
import { Loader2, GitCommit, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import api from '@/lib/api';

interface CommitEntry {
  hash: string;
  message: string;
  date: string;
  relative_date: string;
}

export default function ChangelogPage() {
  const [commits, setCommits] = useState<CommitEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.title = 'Changelog — Sarson Funds CRM';
    fetchChangelog();
  }, []);

  const fetchChangelog = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get('/admin/changelog');
      setCommits(res.data.commits || []);
    } catch (err) {
      setError('Failed to load changelog');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-muted-foreground">
        <p className="text-lg font-semibold">Failed to load changelog</p>
        <p className="text-sm mt-1">{error}</p>
        <Button variant="outline" className="mt-4" onClick={fetchChangelog}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Changelog</h1>
          <p className="text-muted-foreground mt-1">
            Recent development history ({commits.length} commits)
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchChangelog}>
          <RefreshCw className="h-4 w-4 mr-1" />
          Refresh
        </Button>
      </div>

      {/* Timeline */}
      {commits.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <GitCommit className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>No commits found</p>
        </div>
      ) : (
        <div className="relative">
          {/* Timeline line */}
          <div className="absolute left-4 top-0 bottom-0 w-px bg-border" />

          {/* Commit entries */}
          <div className="space-y-4">
            {commits.map((commit, idx) => (
              <div key={commit.hash + idx} className="relative pl-10">
                {/* Timeline dot */}
                <div className="absolute left-2 top-2 w-5 h-5 rounded-full bg-background border-2 border-[#253a52] flex items-center justify-center">
                  <div className="w-2 h-2 rounded-full bg-[#253a52]" />
                </div>

                {/* Commit content */}
                <div className="bg-card border rounded-lg p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-foreground">
                        {commit.message}
                      </p>
                      <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                        <code className="px-1.5 py-0.5 bg-muted rounded font-mono">
                          {commit.hash}
                        </code>
                        <span title={commit.date}>{commit.relative_date}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
