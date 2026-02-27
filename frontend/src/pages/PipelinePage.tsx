import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  DndContext,
  DragOverlay,
  closestCorners,
  type DragStartEvent,
  type DragEndEvent,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import { useDroppable } from '@dnd-kit/core';
import { useDraggable } from '@dnd-kit/core';
import { toast } from 'sonner';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

interface Deal {
  id: string;
  title: string;
  stage: string;
  amount: number | null;
  currency: string;
  company_id: string | null;
  owner_id: string | null;
  expected_close: string | null;
  created_at: string;
  // Populated
  company_name?: string;
  contact_name?: string;
}

const STAGES = [
  'sourced',
  'screening',
  'diligence',
  'term_sheet',
  'closing',
  'closed_won',
  'closed_lost',
  'passed',
];

const STAGE_LABELS: Record<string, string> = {
  sourced: 'Sourced',
  screening: 'Screening',
  diligence: 'Diligence',
  term_sheet: 'Term Sheet',
  closing: 'Closing',
  closed_won: 'Closed Won',
  closed_lost: 'Closed Lost',
  passed: 'Passed',
};

const STAGE_COLORS: Record<string, string> = {
  sourced: 'border-t-blue-400',
  screening: 'border-t-cyan-400',
  diligence: 'border-t-amber-400',
  term_sheet: 'border-t-orange-400',
  closing: 'border-t-purple-400',
  closed_won: 'border-t-green-500',
  closed_lost: 'border-t-red-400',
  passed: 'border-t-gray-400',
};

function formatCurrency(amount: number | null, currency = 'USD') {
  if (!amount) return '—';
  return new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 0 }).format(amount);
}

// ── Droppable Column ──────────────────────────────────────────────────────

function StageColumn({ stage, deals }: { stage: string; deals: Deal[] }) {
  const { setNodeRef, isOver } = useDroppable({ id: stage });
  const totalValue = deals.reduce((sum, d) => sum + (d.amount || 0), 0);

  return (
    <div
      ref={setNodeRef}
      className={`flex flex-col min-w-[280px] max-w-[320px] bg-muted/30 rounded-lg p-3 border-t-3 ${STAGE_COLORS[stage] || ''} ${isOver ? 'ring-2 ring-primary' : ''}`}
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold">{STAGE_LABELS[stage] || stage}</h3>
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs">{deals.length}</Badge>
          {totalValue > 0 && (
            <span className="text-xs text-muted-foreground">{formatCurrency(totalValue)}</span>
          )}
        </div>
      </div>
      <div className="space-y-2 flex-1 min-h-[100px]">
        {deals.length === 0 ? (
          <p className="text-xs text-muted-foreground text-center py-6">No deals</p>
        ) : (
          deals.map((deal) => (
            <DealCard key={deal.id} deal={deal} />
          ))
        )}
      </div>
    </div>
  );
}

// ── Draggable Deal Card ───────────────────────────────────────────────────

function DealCard({ deal, overlay }: { deal: Deal; overlay?: boolean }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: deal.id,
    data: deal,
  });

  const style = transform
    ? { transform: `translate(${transform.x}px, ${transform.y}px)` }
    : undefined;

  return (
    <div
      ref={overlay ? undefined : setNodeRef}
      {...(overlay ? {} : { ...attributes, ...listeners })}
      style={style}
      className={`bg-card border rounded-md p-3 cursor-grab active:cursor-grabbing shadow-sm ${isDragging ? 'opacity-50' : ''}`}
    >
      <p className="text-sm font-medium truncate">{deal.title}</p>
      {(deal.contact_name || deal.company_name) && (
        <p className="text-xs text-muted-foreground mt-1">{deal.contact_name || deal.company_name}</p>
      )}
      <div className="flex items-center justify-between mt-2">
        <span className="text-sm font-semibold">{formatCurrency(deal.amount)}</span>
        <span className="text-xs text-muted-foreground">
          {Math.max(0, Math.floor((Date.now() - new Date(deal.created_at).getTime()) / 86400000))}d
        </span>
      </div>
    </div>
  );
}

// ── Create/Edit Modal ─────────────────────────────────────────────────────

function DealModal({
  open,
  onClose,
  deal,
}: {
  open: boolean;
  onClose: () => void;
  deal?: Deal | null;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    title: deal?.title || '',
    amount: deal?.amount?.toString() || '',
    stage: deal?.stage || 'sourced',
    expected_close: deal?.expected_close || '',
  });

  const mutation = useMutation({
    mutationFn: async (data: Record<string, unknown>) => {
      if (deal) {
        await api.patch(`/deals/${deal.id}`, data);
      } else {
        await api.post('/deals', data);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['deals'] });
      toast.success(deal ? 'Deal updated' : 'Deal created');
      onClose();
    },
    onError: () => {
      toast.error('Failed to save deal');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate({
      title: form.title,
      amount: form.amount ? parseFloat(form.amount) : null,
      stage: form.stage,
      expected_close: form.expected_close || null,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{deal ? 'Edit Deal' : 'New Deal'}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label>Title</Label>
            <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
          </div>
          <div>
            <Label>Amount</Label>
            <Input type="number" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
          </div>
          <div>
            <Label>Stage</Label>
            <select
              className="w-full border rounded-md p-2 text-sm"
              value={form.stage}
              onChange={(e) => setForm({ ...form, stage: e.target.value })}
            >
              {STAGES.map((s) => (
                <option key={s} value={s}>{STAGE_LABELS[s]}</option>
              ))}
            </select>
          </div>
          <div>
            <Label>Expected Close</Label>
            <Input type="date" value={form.expected_close} onChange={(e) => setForm({ ...form, expected_close: e.target.value })} />
          </div>
          <Button type="submit" disabled={mutation.isPending}>
            {deal ? 'Update' : 'Create'} Deal
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ── Main Pipeline Page ────────────────────────────────────────────────────

export default function PipelinePage() {
  const queryClient = useQueryClient();
  const [activeDeal, setActiveDeal] = useState<Deal | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editDeal, setEditDeal] = useState<Deal | null>(null);

  useEffect(() => { document.title = 'Pipeline — Sarson Funds CRM'; }, []);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  );

  const { data: deals = [] } = useQuery<Deal[]>({
    queryKey: ['deals'],
    queryFn: async () => {
      const res = await api.get('/deals');
      return Array.isArray(res.data) ? res.data : res.data.data || [];
    },
  });

  const moveMutation = useMutation({
    mutationFn: async ({ dealId, stage }: { dealId: string; stage: string }) => {
      await api.patch(`/deals/${dealId}/stage`, { stage });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['deals'] });
      toast.success('Deal moved');
    },
    onError: () => {
      toast.error('Failed to move deal');
    },
  });

  const dealsByStage = STAGES.reduce<Record<string, Deal[]>>((acc, stage) => {
    acc[stage] = deals.filter((d) => d.stage === stage);
    return acc;
  }, {});

  const handleDragStart = (event: DragStartEvent) => {
    setActiveDeal(event.active.data.current as Deal);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    setActiveDeal(null);
    const { active, over } = event;
    if (!over) return;

    const dealId = active.id as string;
    const newStage = over.id as string;
    const deal = deals.find((d) => d.id === dealId);

    if (deal && deal.stage !== newStage && STAGES.includes(newStage)) {
      moveMutation.mutate({ dealId, stage: newStage });
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Pipeline</h1>
        <Button onClick={() => { setEditDeal(null); setModalOpen(true); }}>
          + New Deal
        </Button>
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <div className="flex gap-4 overflow-x-auto pb-4">
          {STAGES.map((stage) => (
            <StageColumn key={stage} stage={stage} deals={dealsByStage[stage] || []} />
          ))}
        </div>

        <DragOverlay>
          {activeDeal ? <DealCard deal={activeDeal} overlay /> : null}
        </DragOverlay>
      </DndContext>

      <DealModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        deal={editDeal}
      />
    </div>
  );
}
