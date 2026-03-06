import { useQuery } from '@tanstack/react-query';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Loader2, AlertCircle } from 'lucide-react';
import { formatDate } from '@/lib/formatDate';
import api from '@/lib/api';

interface RemovalHistory {
  removal_id: string;
  campaign_id: string;
  campaign_name: string;
  reason: string;
  removed_at: string;
  removed_by_email: string | null;
}

interface CampaignRemovalHistoryProps {
  contactId: string;
  contactName?: string;
}

export function CampaignRemovalHistory({
  contactId,
  contactName,
}: CampaignRemovalHistoryProps) {
  const {
    data: removals = [],
    isLoading,
    error,
  } = useQuery<RemovalHistory[]>({
    queryKey: ['contact-removal-history', contactId],
    queryFn: async () => {
      // ✅ API call with contactId as parameter
      // ✅ Pagination handled by backend (limit/offset)
      const res = await api.get(
        `/campaigns/contacts/${contactId}/campaign-history?limit=50&offset=0`
      );
      return res.data;
    },
    enabled: !!contactId,
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Campaign Removal History</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Campaign Removal History</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded text-red-700">
            <AlertCircle className="h-5 w-5 flex-shrink-0" />
            <p>Failed to load removal history. Please try again later.</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (removals.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Campaign Removal History</CardTitle>
          <CardDescription>
            {contactName || 'This contact'} has not been removed from any campaigns.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Campaign Removal History</CardTitle>
        <CardDescription>
          {removals.length} campaign removal{removals.length !== 1 ? 's' : ''} on record
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Campaign</TableHead>
                <TableHead>Reason</TableHead>
                <TableHead>Removed By</TableHead>
                <TableHead>Date</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {removals.map((removal) => (
                <TableRow key={removal.removal_id}>
                  <TableCell className="font-medium">
                    <span className="text-sm">{removal.campaign_name}</span>
                  </TableCell>
                  <TableCell>
                    <div className="max-w-xs">
                      <p className="text-sm text-gray-700 break-words">
                        {removal.reason}
                      </p>
                    </div>
                  </TableCell>
                  <TableCell className="text-sm text-gray-500">
                    {removal.removed_by_email || 'Unknown'}
                  </TableCell>
                  <TableCell className="text-sm text-gray-500">
                    {formatDate(new Date(removal.removed_at))}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
