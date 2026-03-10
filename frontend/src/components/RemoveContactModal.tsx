import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Loader2, AlertCircle } from 'lucide-react';

interface RemoveContactModalProps {
  open: boolean;
  onClose: () => void;
  campaignId: string;
  contactId: string;
  contactName: string;
  onSuccess: () => void;
}

const REMOVAL_REASONS = [
  { value: 'completed', label: 'Completed' },
  { value: 'no', label: 'Not Interested' },
  { value: 'dnc', label: 'Do Not Contact' },
] as const;

export function RemoveContactModal({
  open,
  onClose,
  campaignId,
  contactId,
  contactName,
  onSuccess,
}: RemoveContactModalProps) {
  const [reason, setReason] = useState('completed');
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: async () => {
      await api.post(
        `/sales-campaigns/${campaignId}/remove-contact`,
        { contact_id: contactId, reason: reason }
      );
    },
    onSuccess: () => {
      toast.success('Contact removed from campaign');
      queryClient.invalidateQueries({ queryKey: ['sales-campaign-contacts', campaignId] });
      queryClient.invalidateQueries({ queryKey: ['sales-campaigns'] });
      queryClient.invalidateQueries({ queryKey: ['contact-campaigns', contactId] });
      setReason('completed');
      onSuccess();
      onClose();
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Failed to remove contact');
    },
  });

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Remove Contact from Campaign</DialogTitle>
          <DialogDescription>
            You're removing <span className="font-medium">{contactName}</span> from this campaign.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="reason" className="text-sm font-medium">
              Reason for Removal *
            </Label>
            <Select value={reason} onValueChange={setReason}>
              <SelectTrigger id="reason">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {REMOVAL_REASONS.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              This reason will be recorded in the contact's campaign history.
            </p>
          </div>

          <div className="flex items-start gap-2 text-sm text-amber-600 bg-amber-50 p-2 rounded">
            <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
            <span>This action cannot be undone. The contact's campaign history will be updated.</span>
          </div>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
          >
            {mutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Removing...
              </>
            ) : (
              'Remove Contact'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
