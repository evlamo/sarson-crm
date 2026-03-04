export interface HelpArticle {
  id: string;
  title: string;
  category: string;
  keywords: string[];
  content: string;
  relevantPaths: string[];
}

export const helpArticles: HelpArticle[] = [
  // Getting Started
  {
    id: 'getting-started-login',
    title: 'How to Log In',
    category: 'Getting Started',
    keywords: ['login', 'sign in', 'password', 'access', 'authentication'],
    relevantPaths: ['/login'],
    content: `# How to Log In

Welcome to Sarson Funds CRM! Here's how to access your account:

1. Go to the login page at your CRM URL
2. Enter your email address
3. Enter your password
4. Click **Sign In**

## Forgot your password?

Contact your administrator to reset your password. They can send you a new invite link.

## First time logging in?

If you received an invite email, click the link to set up your account. You'll need to create a password before you can log in.

## Having trouble?

- Make sure you're using the correct email address
- Check that Caps Lock is off
- Try clearing your browser cache
- Contact your admin if you're still stuck`
  },
  {
    id: 'getting-started-navigation',
    title: 'Navigating the CRM',
    category: 'Getting Started',
    keywords: ['navigation', 'sidebar', 'menu', 'pages', 'dashboard'],
    relevantPaths: ['/', '/contacts', '/companies'],
    content: `# Navigating the CRM

The CRM is organized with a sidebar navigation on the left.

## Main Sections

- **Contacts** — Your contact database. Search, filter, and manage all contacts.
- **Companies** — Organizations linked to contacts. Track company relationships.
- **Google Ads** — View lead generation metrics from Google Ads campaigns.
- **Email Campaigns** — Create and send bulk email campaigns.
- **Sales Campaigns** — Track outbound sales efforts and assignments.
- **Campaign Stats** — View email open rates, clicks, and performance.
- **Lists** — Create segmented contact lists for targeting.
- **Activity** — View recent actions across the CRM.
- **Tags** — Manage contact tags for categorization.
- **Import** — Upload CSV files to add contacts in bulk.

## Admin Section

If you're an admin, you'll see additional options:
- **Users** — Manage team member accounts
- **Team & Invites** — Invite new users
- **API Controls** — Manage API credentials
- **Sheets Sync** — Configure Google Sheets integration

## Keyboard Shortcuts

Press \`?\` anywhere to see available keyboard shortcuts.`
  },
  {
    id: 'getting-started-first-contact',
    title: 'Creating Your First Contact',
    category: 'Getting Started',
    keywords: ['first', 'create', 'new', 'contact', 'add'],
    relevantPaths: ['/contacts'],
    content: `# Creating Your First Contact

Adding contacts to the CRM is simple.

## Quick Add

1. Go to the **Contacts** page
2. Click the **+ New Contact** button (or press \`N\`)
3. Fill in the required fields:
   - **Name** (first and last)
   - **Email** (required for email campaigns)
4. Add optional information:
   - Phone number
   - Company (link to existing or create new)
   - Tags for categorization
5. Click **Save**

## Tips

- Use tags to categorize contacts (e.g., "Prospect", "Client", "VIP")
- Link contacts to companies to see all POCs at a glance
- Add notes to track conversation history
- Set the status (Active, Inactive, DNC) appropriately`
  },

  // Contacts
  {
    id: 'contacts-overview',
    title: 'Managing Contacts',
    category: 'Contacts',
    keywords: ['contacts', 'manage', 'edit', 'view', 'list'],
    relevantPaths: ['/contacts'],
    content: `# Managing Contacts

The Contacts page is your central hub for managing all contacts in the CRM.

## Viewing Contacts

The contact list shows:
- Name and email
- Company affiliation
- Tags
- Status (Active, Inactive, DNC)
- Assigned rep

## Filtering & Searching

Use the search bar to find contacts by name or email. Use filters to narrow by:
- Status
- Tags
- Assigned rep
- Company

## Bulk Actions

Select multiple contacts to:
- Add/remove tags
- Assign to a rep
- Add to a list
- Export to CSV

## Contact Detail View

Click any contact to see their full profile including:
- All contact information
- Activity timeline
- Notes and history
- Company association
- Campaign interactions`
  },
  {
    id: 'contacts-editing',
    title: 'Editing Contact Information',
    category: 'Contacts',
    keywords: ['edit', 'update', 'change', 'modify', 'contact'],
    relevantPaths: ['/contacts'],
    content: `# Editing Contact Information

You can edit contacts directly from their detail page.

## Inline Editing

Most fields support inline editing:
1. Click on any editable field
2. Make your changes
3. Press Enter or click away to save

## Editable Fields

- Name (first, last)
- Email
- Phone
- Company
- Status
- Tags
- Notes
- Custom fields

## Important Notes

- Email changes are logged in the audit trail
- Status changes (especially to DNC) affect campaign eligibility
- All edits are automatically saved
- You can't edit contacts you don't have permission for`
  },
  {
    id: 'contacts-tagging',
    title: 'Tagging Contacts',
    category: 'Contacts',
    keywords: ['tags', 'label', 'categorize', 'organize'],
    relevantPaths: ['/contacts', '/tags'],
    content: `# Tagging Contacts

Tags help you categorize and segment contacts.

## Adding Tags

1. Open a contact's detail page
2. Click the tags section
3. Select existing tags or type to create new ones
4. Tags are saved automatically

## Bulk Tagging

1. Select multiple contacts from the list
2. Use the bulk actions menu
3. Choose "Add Tags" or "Remove Tags"
4. Select the tags to apply

## Managing Tags

Go to the **Tags** page to:
- View all tags and usage counts
- Rename tags
- Delete unused tags
- Merge duplicate tags

## Best Practices

- Use consistent naming conventions
- Don't over-tag — keep it simple
- Review tags periodically for cleanup
- Consider tag hierarchy (e.g., "Industry: Tech")`
  },
  {
    id: 'contacts-filtering',
    title: 'Filtering & Searching Contacts',
    category: 'Contacts',
    keywords: ['filter', 'search', 'find', 'query', 'sort'],
    relevantPaths: ['/contacts'],
    content: `# Filtering & Searching Contacts

Find exactly the contacts you need with powerful search and filters.

## Quick Search

The search bar finds contacts by:
- Name (first or last)
- Email address
- Company name

Press \`/\` to focus the search bar instantly.

## Filters

Click the filter icon to access:
- **Status** — Active, Inactive, or DNC
- **Tags** — Filter by one or more tags
- **Rep** — Assigned representative
- **Date Range** — Created or modified dates

## Combining Filters

Multiple filters work together (AND logic). For example:
- Status = Active AND Tags = "VIP" AND Rep = "John"

## Sorting

Click column headers to sort:
- Name (A-Z or Z-A)
- Email
- Created date
- Last activity

## Saving Searches

Create a List to save frequently used filter combinations.`
  },
  {
    id: 'contacts-exporting',
    title: 'Exporting Contacts',
    category: 'Contacts',
    keywords: ['export', 'download', 'csv', 'excel', 'backup'],
    relevantPaths: ['/contacts', '/sheets'],
    content: `# Exporting Contacts

Export contacts for backup, analysis, or use in other tools.

## CSV Export

1. Go to the **Contacts** page
2. Apply any filters to narrow your selection
3. Click **Export** or use bulk actions
4. Download the CSV file

## What's Included

Exports include:
- All contact fields (name, email, phone, etc.)
- Company name
- Tags (comma-separated)
- Status
- Created/updated dates

## Google Sheets Sync

For live, two-way sync, use the **Sheets Sync** feature:
1. Go to Admin → Sheets Sync
2. Connect your Google account
3. Select or create a spreadsheet
4. Configure sync settings
5. Changes flow both ways automatically

See the Sheets Sync guide for detailed setup.`
  },

  // Companies
  {
    id: 'companies-overview',
    title: 'Managing Companies',
    category: 'Companies',
    keywords: ['company', 'organization', 'business', 'manage'],
    relevantPaths: ['/companies'],
    content: `# Managing Companies

Companies represent organizations that your contacts belong to.

## Viewing Companies

The Companies page shows:
- Company name
- Number of contacts (POCs)
- Primary contact
- Industry/type

## Creating a Company

1. Click **+ New Company**
2. Enter the company name
3. Add optional details:
   - Website
   - Industry
   - Address
   - Notes
4. Click **Save**

## Linking Contacts

Contacts can be linked to companies:
- From the contact edit screen, select a company
- From the company detail, add contacts as POCs
- Primary contact can be designated`
  },
  {
    id: 'companies-poc',
    title: 'Managing Points of Contact',
    category: 'Companies',
    keywords: ['poc', 'point of contact', 'primary', 'contacts'],
    relevantPaths: ['/companies'],
    content: `# Managing Points of Contact

Track multiple contacts (POCs) at each company.

## What's a POC?

A Point of Contact is any person at a company you interact with. A company might have:
- Primary contact (main relationship)
- Secondary contacts (other stakeholders)
- Former contacts (no longer at company)

## Setting Primary Contact

1. Open the company detail page
2. View the linked contacts
3. Click "Set as Primary" on any contact
4. Only one primary per company

## Why It Matters

- Primary contacts show first in lists
- Email campaigns can target primary POCs
- Helps focus communication efforts
- Important for account management`
  },

  // Lists
  {
    id: 'lists-overview',
    title: 'Creating and Managing Lists',
    category: 'Lists',
    keywords: ['list', 'segment', 'group', 'create', 'manage'],
    relevantPaths: ['/lists'],
    content: `# Creating and Managing Lists

Lists are saved groups of contacts for targeting campaigns or organization.

## Creating a List

1. Go to the **Lists** page
2. Click **+ New List**
3. Enter a name and optional description
4. Save the list

## Adding Contacts

**Manual Selection:**
1. Go to Contacts
2. Select contacts using checkboxes
3. Use bulk actions → Add to List
4. Select your list

**Filter-Based:**
1. Apply filters on Contacts page
2. Select all matching contacts
3. Add to list

## List Types

- **Static Lists** — Manually curated, contacts stay until removed
- **Dynamic Lists** — Auto-update based on filter criteria (coming soon)

## Using Lists

Lists can be used as:
- Email campaign recipients
- Sales campaign targets
- Export groups
- Reporting segments`
  },
  {
    id: 'lists-filters',
    title: 'Using Filters in Lists',
    category: 'Lists',
    keywords: ['filter', 'criteria', 'segment', 'dynamic'],
    relevantPaths: ['/lists'],
    content: `# Using Filters in Lists

Build targeted lists using filter criteria.

## Filter Options

When creating a list, filter by:
- **Status** — Active, Inactive, DNC
- **Tags** — Include/exclude specific tags
- **Rep** — Assigned representative
- **Company** — Specific company or any/none
- **Date** — Created or modified date range
- **Campaign** — Previous campaign interaction

## Combining Filters

Use AND/OR logic:
- AND: All conditions must match
- OR: Any condition can match

Example: "Active contacts" AND ("VIP" OR "Client" tag)

## Preview Results

Before saving, preview how many contacts match your criteria. Adjust filters until you have the right segment.

## Best Practices

- Name lists descriptively (e.g., "Q1 2024 Webinar Invites")
- Review list size before campaigns
- Update static lists periodically
- Archive old lists to keep things tidy`
  },

  // Campaigns
  {
    id: 'campaigns-types',
    title: 'Sales vs Email Campaigns',
    category: 'Campaigns',
    keywords: ['campaign', 'sales', 'email', 'type', 'difference'],
    relevantPaths: ['/campaigns', '/sales-campaigns'],
    content: `# Sales vs Email Campaigns

The CRM supports two types of campaigns with different purposes.

## Email Campaigns

Found under **Email Campaigns** in the sidebar.

- Send bulk emails to lists of contacts
- Track opens, clicks, and replies
- Use templates for consistent messaging
- Schedule sends for optimal timing
- Automated unsubscribe handling

Best for: Newsletters, announcements, marketing content

## Sales Campaigns

Found under **Sales Campaigns** in the sidebar.

- Assign contacts to reps for outreach
- Track individual touchpoints
- Manage pipeline stages
- Log calls, emails, and meetings
- Team performance reporting

Best for: Outbound sales, lead follow-up, account management

## When to Use Which

| Scenario | Campaign Type |
|----------|---------------|
| Newsletter blast | Email Campaign |
| New product announcement | Email Campaign |
| Lead follow-up calls | Sales Campaign |
| Demo scheduling | Sales Campaign |
| Event invitation | Email Campaign |
| Personal outreach | Sales Campaign |`
  },
  {
    id: 'campaigns-dnc',
    title: 'Do Not Contact (DNC) Rules',
    category: 'Campaigns',
    keywords: ['dnc', 'do not contact', 'unsubscribe', 'compliance', 'opt-out'],
    relevantPaths: ['/campaigns', '/sales-campaigns', '/contacts'],
    content: `# Do Not Contact (DNC) Rules

The CRM enforces DNC rules to ensure compliance and respect contact preferences.

## What is DNC?

DNC (Do Not Contact) is a status that prevents contacts from receiving:
- Bulk email campaigns
- Sales campaign assignments
- Automated outreach

## How Contacts Become DNC

- **Manual** — User sets status to DNC
- **Unsubscribe** — Contact clicks unsubscribe link
- **Bounce** — Email hard bounces
- **Complaint** — Marked as spam

## DNC Enforcement

- DNC contacts are automatically excluded from campaigns
- They won't appear in campaign recipient lists
- Attempting to add them shows a warning
- All DNC changes are logged in the audit trail

## Removing DNC Status

In rare cases (confirmed re-consent):
1. Open the contact
2. Change status from DNC to Active
3. Add a note explaining the reason
4. This action is logged

## Best Practices

- Never manually override DNC without documented consent
- Review DNC reports monthly
- Train team on compliance requirements
- Keep unsubscribe links in all emails`
  },

  // Sheets Sync
  {
    id: 'sheets-setup',
    title: 'Setting Up Google Sheets Sync',
    category: 'Sheets Sync',
    keywords: ['sheets', 'google', 'setup', 'connect', 'integration'],
    relevantPaths: ['/sheets'],
    content: `# Setting Up Google Sheets Sync

Sync contacts bidirectionally with Google Sheets.

## Prerequisites

- Admin access to the CRM
- Google account with Sheets access
- Service account credentials (from your admin)

## Setup Steps

1. Go to **Admin → Sheets Sync**
2. Click **Configure Service Account**
3. Upload your service account JSON file
4. Share your target spreadsheet with the service account email
5. Enter the spreadsheet ID
6. Click **Connect**

## Service Account Setup

If you need to create a service account:
1. Go to Google Cloud Console
2. Create a new project (or use existing)
3. Enable Google Sheets API
4. Create a service account
5. Download the JSON key file
6. Share your spreadsheet with the service account email

## Column Mapping

The sync uses standard column names:
- First Name, Last Name
- Email, Phone
- Company
- Tags (comma-separated)
- Status

Custom columns can be mapped in settings.`
  },
  {
    id: 'sheets-conflicts',
    title: 'Resolving Sync Conflicts',
    category: 'Sheets Sync',
    keywords: ['conflict', 'sync', 'resolve', 'error', 'mismatch'],
    relevantPaths: ['/sheets'],
    content: `# Resolving Sync Conflicts

When the same contact is edited in both places, conflicts can occur.

## What Causes Conflicts

- Contact edited in CRM and Sheets between syncs
- Duplicate email addresses
- Invalid data formats
- Network interruptions

## Conflict Resolution

The sync shows conflicts in the dashboard:
1. Go to **Sheets Sync**
2. View the Conflicts tab
3. For each conflict, choose:
   - **Keep CRM** — Use CRM data
   - **Keep Sheet** — Use Sheets data
   - **Merge** — Combine changes (when possible)
4. Click Resolve

## Preventing Conflicts

- Sync frequently (reduces window for conflicts)
- Designate primary edit location
- Avoid editing same contacts in both places
- Use CRM as source of truth for critical data

## Error Recovery

If sync fails:
1. Check internet connectivity
2. Verify service account permissions
3. Review error messages in sync log
4. Re-authorize if needed
5. Contact admin for persistent issues`
  },

  // Admin
  {
    id: 'admin-users',
    title: 'Managing Users',
    category: 'Admin',
    keywords: ['user', 'admin', 'manage', 'team', 'account'],
    relevantPaths: ['/admin/users'],
    content: `# Managing Users

Control who can access the CRM and what they can do.

## User Roles

- **Owner** — Full access, can manage all settings
- **Admin** — Full access, can manage users
- **User** — Standard access, limited admin features
- **Viewer** — Read-only access

## Viewing Users

Go to **Admin → Users** to see:
- All team members
- Their roles
- Last active date
- Account status

## Editing Users

Click any user to:
- Change their role
- Update their name
- Disable their account
- Reset their password (via new invite)

## Deactivating Users

Deactivated users:
- Cannot log in
- Retain their data history
- Can be reactivated later
- Free up a seat on your plan`
  },
  {
    id: 'admin-invites',
    title: 'Inviting New Users',
    category: 'Admin',
    keywords: ['invite', 'new', 'user', 'add', 'team'],
    relevantPaths: ['/admin/invites'],
    content: `# Inviting New Users

Add team members to your CRM.

## Sending Invites

1. Go to **Admin → Team & Invites**
2. Click **+ Invite User**
3. Enter their email address
4. Select their role
5. Click **Send Invite**

## Invite Process

1. User receives email with invite link
2. They click the link
3. Create their password
4. Complete profile setup
5. Start using the CRM

## Managing Invites

View pending invites to:
- See who hasn't accepted yet
- Resend invite emails
- Cancel invites
- Change assigned role

## Best Practices

- Use work email addresses
- Set appropriate role from the start
- Follow up if invite isn't accepted
- Provide onboarding resources`
  },
  {
    id: 'admin-rbac',
    title: 'Role-Based Access Control',
    category: 'Admin',
    keywords: ['rbac', 'permissions', 'access', 'role', 'security'],
    relevantPaths: ['/admin/users'],
    content: `# Role-Based Access Control

Understand what each role can and cannot do.

## Permission Matrix

| Action | Viewer | User | Admin | Owner |
|--------|--------|------|-------|-------|
| View contacts | ✓ | ✓ | ✓ | ✓ |
| Edit contacts | — | ✓ | ✓ | ✓ |
| Delete contacts | — | — | ✓ | ✓ |
| Manage campaigns | — | ✓ | ✓ | ✓ |
| View admin pages | — | — | ✓ | ✓ |
| Manage users | — | — | ✓ | ✓ |
| Billing & settings | — | — | — | ✓ |

## Changing Roles

Only Admins and Owners can change roles:
1. Go to Admin → Users
2. Click on a user
3. Select new role
4. Save changes

## Security Notes

- Principle of least privilege — give minimum needed access
- Review roles quarterly
- Remove access promptly when people leave
- Log sensitive actions for audit`
  },
  {
    id: 'admin-audit',
    title: 'Viewing the Audit Log',
    category: 'Admin',
    keywords: ['audit', 'log', 'history', 'track', 'activity'],
    relevantPaths: ['/activity'],
    content: `# Viewing the Audit Log

Track all changes made in the CRM.

## What's Logged

- Contact creates, edits, deletes
- Status changes (especially DNC)
- User logins and logouts
- Campaign sends
- Import operations
- Settings changes
- User management actions

## Viewing the Log

Go to **Activity** in the sidebar to see:
- Recent actions across all users
- Filter by date, user, or action type
- Search for specific records

## Log Entry Details

Each entry shows:
- Timestamp
- User who performed action
- Action type
- Affected record
- Before/after values (for edits)

## Retention

Audit logs are retained for 2 years. Contact admin for older records or exports.

## Best Practices

- Review logs regularly for unusual activity
- Use for compliance audits
- Investigate issues by tracing actions
- Export logs for external analysis`
  }
  // Version History
  {
    id: 'contacts-version-history',
    title: 'Version History & Reverting Changes',
    category: 'Contacts',
    keywords: ['version', 'history', 'revert', 'undo', 'restore', 'audit', 'change'],
    relevantPaths: ['/contacts'],
    content: `# Version History & Reverting Changes

Every field change on a contact is tracked automatically. The CRM maintains a full audit trail so you can always see what changed, when, and who made the change.

## Viewing History

1. Open a contact's detail page
2. Click the **History** tab (next to Overview, Notes, etc.)
3. You'll see a chronological list of all field changes
4. Each entry shows:
   - The field that changed
   - The previous value
   - The new value
   - Timestamp of the change
   - Which user made the change

## Reverting a Field

To restore a previous value:
1. Find the change you want to undo in the History tab
2. Click the **Revert** button on that entry
3. Confirm the revert in the dialog
4. The field is instantly restored to its previous value

**Note:** Reverting is itself a logged action — the history will show that a revert occurred, who did it, and when.

## Bulk Rollbacks

For large-scale rollbacks, the system runs automated database snapshots every 8 hours. Admins can restore from these snapshots to roll back bulk operations or recover from import errors. Contact your admin if you need a bulk rollback.`
  },

  // Sales Campaigns Overview
  {
    id: 'campaigns-sales-overview',
    title: 'How Sales Campaigns Work',
    category: 'Campaigns',
    keywords: ['sales campaign', 'outreach', 'pipeline', 'assign', 'status', 'workflow'],
    relevantPaths: ['/sales-campaigns'],
    content: `# How Sales Campaigns Work

Sales campaigns are containers for organized outbound efforts. Each campaign holds a set of contacts and can be linked to one or more email campaigns.

## Contact Statuses

Every contact in a sales campaign has their own per-campaign status:

| Status | Meaning |
|--------|---------|
| **Active** | In progress — rep is working this contact |
| **Completed** | Outreach finished successfully |
| **No** | Contact declined or not interested |
| **Excluded** | Manually excluded from this campaign |
| **Paused** | Temporarily paused for this contact |

## The Fresh Slate Rule

This is important: **statuses are per-campaign, not global.**

A contact marked "No" or "Completed" in Campaign A has **zero effect** on their eligibility for Campaign B. When a contact is added to a new campaign, they start fresh — their status in other campaigns doesn't carry over.

This lets you run multiple campaigns against the same contact list without past results blocking future opportunities.

## Creating a Sales Campaign

1. Go to **Sales Campaigns** in the sidebar
2. Click **+ New Campaign**
3. Give it a name and optional description
4. Save

## Adding Contacts

You can add contacts to a campaign three ways:
- **By Tag** — Add all contacts with a specific tag
- **By List** — Add contacts from a saved list
- **Manual** — Search and add contacts one by one

## Linking Email Campaigns

Each sales campaign can be linked to email campaigns. When an email send runs, it respects the per-contact status — contacts marked No, Excluded, or Completed in the sales campaign will be skipped by the linked email campaigns.`
  },

  // Campaign Exclusion & DNC Logic
  {
    id: 'campaigns-exclusion-logic',
    title: 'Campaign Exclusion & DNC Logic',
    category: 'Campaigns',
    keywords: ['exclusion', 'dnc', 'do not contact', 'fresh slate', 'campaign status', 'eligible'],
    relevantPaths: ['/sales-campaigns', '/campaigns'],
    content: `# Campaign Exclusion & DNC Logic

The CRM uses a two-tier system for controlling who receives outreach.

## Tier 1 — Master DNC (Global)

The Master DNC flag is a global kill switch. A contact marked DNC:
- Is blocked from **all** campaigns and email sends system-wide
- Cannot receive any automated or bulk outreach
- Is set manually by an admin, or automatically when a contact unsubscribes

This is a hard block and takes precedence over everything else.

## Tier 2 — Per-Campaign Status (Local)

Each contact has an independent status within each campaign. The statuses that block sends within a campaign:

| Status | Blocks this campaign? | Blocks other campaigns? |
|--------|----------------------|------------------------|
| Active | No | No |
| Paused | Yes | No |
| No | Yes | No |
| Completed | Yes | No |
| Excluded | Yes | No |

**Key point:** A "No" or "Completed" in Campaign A does NOT affect Campaign B. Contacts always start fresh in each new campaign (the Fresh Slate Rule).

## How Eligible-Contact Filtering Works

When a campaign email send is triggered, the system filters recipients:
1. Remove all contacts with Master DNC = true
2. Remove contacts whose status in this campaign is No, Completed, Excluded, or Paused
3. The remaining contacts are the eligible send list

## Checking Eligibility

On a campaign detail page, the contacts list shows current status for each contact. Use the status filter to see which contacts are eligible vs. excluded.`
  },

  // Google Sheets Two-Way Sync (detailed)
  {
    id: 'sheets-two-way-sync',
    title: 'How Google Sheets Two-Way Sync Works',
    category: 'Sheets Sync',
    keywords: ['sheets', 'sync', 'two-way', 'bidirectional', 'import', 'export', 'conflict'],
    relevantPaths: ['/sheets'],
    content: `# How Google Sheets Two-Way Sync Works

The Sheets Sync feature supports full bidirectional sync between the CRM and a Google Sheets spreadsheet.

## Export: CRM → Sheets

When you trigger an export:
- All contacts (or a filtered subset by list) are pushed to the spreadsheet
- Standard fields are included: name, email, phone, company, tags, status, rep
- Rows are keyed by contact ID — re-exports update existing rows rather than creating duplicates
- Filtering by a list lets you export targeted segments

## Import: Sheets → CRM

When you trigger an import (Sheets → CRM):
1. Rows are pulled back from the spreadsheet
2. The system compares each row to the CRM record using the contact ID

**Conflict detection:** If the same contact was edited in both the CRM and the sheet between syncs, a conflict is flagged. You'll see a side-by-side comparison of the two values for each conflicting field.

**Conflict resolution:** An admin reviews each conflict and picks which value wins — CRM version or Sheets version — on a field-by-field basis.

## Special Row Cases

| Row type | What happens |
|----------|-------------|
| ID in sheet matches CRM contact | Updates the contact |
| ID in sheet but contact deleted from CRM | Flagged as **orphan row** — requires manual decision |
| No ID, but has valid email | Treated as **new contact candidate** — you can import or skip |
| No ID, no email | Ignored |

## Security

CSV injection protection is built in — any cell values starting with =, +, -, or @ are sanitized before processing to prevent formula injection attacks.

## Best Practices

- Use the CRM as your source of truth for critical data
- Sync regularly to minimize the conflict window
- Resolve conflicts promptly to keep both systems aligned
- Avoid editing the same contacts in both places simultaneously`
  },

  // Audit Log Details
  {
    id: 'admin-audit-detail',
    title: 'Understanding the Audit Log',
    category: 'Admin',
    keywords: ['audit', 'log', 'trail', 'track', 'who', 'when', 'changed'],
    relevantPaths: ['/activity'],
    content: `# Understanding the Audit Log

Every mutation in the CRM is recorded in the audit log. This gives you a complete trail of who did what and when.

## What's Logged

| Category | Examples |
|----------|---------|
| Contact changes | Create, update, delete any contact field |
| Tags | Add tag to contact, remove tag, rename tag |
| Bulk operations | Bulk tag, bulk assign, bulk status change |
| Campaign activity | Email send, campaign create/edit, contact added/removed |
| DNC changes | Contact set to DNC, DNC removed |
| Import operations | Import started, completed, errors |
| User management | User invited, role changed, deactivated |
| Companies & Lists | Created, edited, deleted |
| Version reverts | Field reverted to previous value via History tab |

## Each Log Entry Contains

- **Timestamp** — Exact date and time
- **Acting user** — Who performed the action
- **Action type** — What kind of change (create, update, delete, etc.)
- **Entity type & ID** — What was affected (Contact ID, Campaign ID, etc.)
- **Before/after values** — What the value was before and after the change

## Filtering the Log

Go to **Activity** in the sidebar and use the filter controls to narrow by:
- **Date range** — Focus on a specific time window
- **User** — See all actions by a specific team member
- **Action type** — Filter to just imports, DNC changes, etc.

## Common Use Cases

- **Compliance audits** — Prove what changed and when for regulatory purposes
- **Debugging** — Trace back unexpected data changes to find the root cause
- **Accountability** — Know which team member made which changes
- **Revert tracking** — When a field is reverted via version history, the revert itself appears as an audit entry

## Retention

Audit logs are retained indefinitely. For large exports or compliance reporting, use the export function or contact your admin.`
  },
];

export const categories = [
  'Getting Started',
  'Contacts',
  'Companies',
  'Lists',
  'Campaigns',
  'Sheets Sync',
  'Admin'
];

export function getArticlesByCategory(category: string): HelpArticle[] {
  return helpArticles.filter(a => a.category === category);
}

export function searchArticles(query: string): HelpArticle[] {
  const lower = query.toLowerCase().trim();
  if (!lower) return [];
  
  return helpArticles.filter(article => {
    return (
      article.title.toLowerCase().includes(lower) ||
      article.keywords.some(k => k.includes(lower)) ||
      article.content.toLowerCase().includes(lower)
    );
  });
}

export function getContextualArticles(pathname: string): HelpArticle[] {
  return helpArticles.filter(article =>
    article.relevantPaths.some(p => pathname.startsWith(p))
  ).slice(0, 3);
}
