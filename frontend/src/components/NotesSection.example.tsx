/**
 * NotesSection Component - Usage Example
 * 
 * This shows how to integrate the NotesSection component into ContactDetailPage.
 * Replace the existing "Notes & Activity" Card in ContactDetailPage.tsx with this.
 */

import { NotesSection } from '@/components/NotesSection';

// ─────────────────────────────────────────────────────────────────────────────
// Example Integration in ContactDetailPage.tsx
// ─────────────────────────────────────────────────────────────────────────────

export function ContactDetailPageExample() {
  const { contactId } = useParams({ from: '/contacts/$contactId' });

  return (
    <div className="container mx-auto px-4 py-6 max-w-7xl">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Contact Summary */}
        <div className="lg:col-span-1 space-y-6">
          {/* ... existing contact info cards ... */}
        </div>

        {/* Right Column - Notes & Activity */}
        <div className="lg:col-span-2 space-y-6">
          {/* ✨ Replace the existing Card with NotesSection component */}
          <NotesSection contactId={contactId} className="min-h-[400px]" />

          {/* ... other cards (Next Step, Background Notes) ... */}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Alternative: Standalone Usage
// ─────────────────────────────────────────────────────────────────────────────

export function StandaloneNotesExample() {
  const contactId = 'some-contact-id';

  return (
    <div className="max-w-4xl mx-auto p-6">
      <NotesSection contactId={contactId} />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// API Requirements
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Backend API endpoints required:
 * 
 * GET /api/v1/contacts/:contactId/activities
 * Response: { data: Activity[] }
 * 
 * POST /api/v1/contacts/:contactId/activities
 * Body: { activity_type: 'note', body: string }
 * Response: { data: Activity }
 * 
 * Activity type:
 * {
 *   id: string;
 *   activity_type: 'note' | 'email' | 'call' | 'meeting' | 'task' | 'document';
 *   subject: string | null;
 *   body: string | null;
 *   performed_at: string;  // ISO 8601
 *   performed_by: string | null;
 * }
 */
