import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';
import { AlertCircle, Loader2 } from 'lucide-react';
import api from '@/lib/api';

interface RemoveContactModalProps {
  isOpen: boolean;
  onClose: () => void;
  campaignId: string;
  contactId: string;
  contactName: string;
  contactEmail: string;
  isDNC?: boolean; // If true, show DNC warning
}

const REMOVAL_REASONS = [
  'Not interested in this campaign',
  'Invalid email address',
  'Requested to be removed',
  'Email bounced',
  'Out of office',
  'Duplicate contact',
  'Wrong contact',
  'Other',
];

export function RemoveContactModal({
  isOpen,
  onClose,
  campaignId,
  contactId,
  contactName,
  contactEmail,
  isDNC = false,
}: RemoveContactModalProps) {
  const queryClient = useQueryClient();
  const [selectedReason, setSelectedReason] = useState('');
  const [customReason, setCustomReason] = useState('');
  const [loading, setLoading] = useState(false);

  const mutation = useMutation({
    mutationFn: async (reason: string) => {
      // ✅ Input validation: reason sanitization handled by backend
      // Frontend validates min/max length for UX feedback
      if (reason.length < 5) {
        throw new Error('Reason must be at least 5 characters');
      }
      if (reason.length > 500) {
        throw new Error('Reason must be 500 characters or less');
      }

      // ✅ XSS Protection: React escapes JSX by default, API call parameterized
      return await api.post(`/campaigns/${campaignId}/remove-contact`, {
        reason,
        contact_id: contactId,
      });
    },
    onSuccess: () => {
      toast.success('Contact removed from campaign');
      queryClient.invalidateQueries({ queryKey: ['campaign', campaignId] });
      queryClient.invalidateQueries({ queryKey: ['contact', contactId] });
      onClose();
      setSelectedReason('');
      setCustomReason('');
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to remove contact';
      toast.error(message);
    },
  });

  const finalReason =
    selectedReason === 'Other'
      ? customReason
      : selectedReason;

  const canSubmit =
    finalReason.length >= 5 &&
    finalReason.length <= 500 &&
    !loading;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setLoading(true);
    try {
      await mutation.mutateAsync(finalReason);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-amber-600" />
            Remove Contact from Campaign
          </DialogTitle>
          <DialogDescription>
            You are about to remove <strong>{contactName}</strong> ({contactEmail}) from this campaign.
            {isDNC && (
              <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                ⚠️ This contact is marked as DNC (Do Not Contact). Ensure compliance before removal.
              </div>
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="reason-select">Reason for Removal</Label>
            <Select value={selectedReason} onValueChange={setSelectedReason}>
              <SelectTrigger id="reason-select">
                <SelectValue placeholder="Select a reason..." />
              </SelectTrigger>
              <SelectContent>
                {REMOVAL_REASONS.map((reason) => (
                  <SelectItem key={reason} value={reason}>
                    {reason}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {selectedReason === 'Other' && (
            <div className="space-y-2">
              <Label htmlFor="custom-reason">Please specify the reason</Label>
              <Textarea
                id="custom-reason"
                placeholder="Enter the reason for removing this contact..."
                value={customReason}
                onChange={(e) => setCustomReason(e.target.value)}
                className="min-h-[100px]"
                maxLength={500}
              />
              <p className="text-xs text-gray-500">
                {customReason.length} / 500 characters
              </p>
            </div>
          )}

          {selectedReason && selectedReason !== 'Other' && (
            <div className="p-3 bg-blue-50 border border-blue-200 rounded text-sm text-blue-700">
              Reason: <strong>{selectedReason}</strong>
            </div>
          )}

          {!selectedReason && (
            <p className="text-sm text-gray-500">
              Please select a reason to continue.
            </p>
          )}
        </div>

        <DialogFooter className="gap-2">
          <Button
            variant="outline"
            onClick={onClose}
            disabled={loading}
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleSubmit}
            disabled={!canSubmit || loading}
            className="gap-2"
          >
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            Remove Contact
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
