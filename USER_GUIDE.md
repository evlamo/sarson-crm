# Sarson CRM - User Guide

## Getting Started

### First Time Setup

1. **Access the CRM**
   - Open your browser to the CRM URL
   - You'll see the login/registration page

2. **Create Your Account**
   - Click "Register"
   - Enter your email (must be @sarsonfunds.com or @speranza.local)
   - Choose a password (minimum 6 characters)
   - Click "Create Account"
   - You can log in immediately (no email verification required)

3. **First Login**
   - The first user becomes the admin automatically
   - You'll see the main dashboard

---

## Importing Contacts

### CSV Import

1. **Prepare Your CSV File**
   - Required columns: `email` (or `Email`)
   - Optional columns: `name`, `first_name`, `last_name`, `phone`, `company`, `title`, `address`, `city`, `state`, `zip`, `country`, `notes`
   - Save as UTF-8 encoded CSV

2. **Import Process**
   - Go to Contacts page
   - Click "Import CSV" button
   - Select your CSV file
   - Map columns to CRM fields
   - Click "Import"
   - System imports in batches of 1000 (progress shown)

3. **After Import**
   - Review imported contacts
   - Add tags for organization
   - Create lists for segmentation

---

## Managing Contacts

### Creating a Contact

1. Click "Add Contact" on Contacts page
2. Fill in required fields (at minimum: email or name)
3. Add company, phone, address as needed
4. Click "Save"

### Editing Contacts

1. Click on any contact to view details
2. Click "Edit" button
3. Update fields
4. Click "Save"

### Bulk Operations

1. Select multiple contacts (checkboxes)
2. Use bulk actions menu:
   - Add to list
   - Add tags
   - Update field
   - Delete

---

## Creating Lists

**Lists** organize contacts for campaigns. Examples: "Hot Leads", "Q1 Prospects", "Newsletter Subscribers"

### Create a List

1. Go to Lists page
2. Click "Create List"
3. Enter list name
4. Add description (optional)
5. Click "Create"

### Add Contacts to List

**Method 1: From Contact Details**
- Open contact → Click "Add to List" → Select list

**Method 2: From Contacts Page**
- Select contacts → Bulk actions → Add to List

**Method 3: During Campaign Creation**
- When adding contacts to campaign, filter by list

---

## Using Tags

**Tags** categorize contacts. Examples: "VIP", "Interested in Product A", "Attended Event"

### Create and Assign Tags

1. On contact page → "Add Tag"
2. Type tag name
3. Press Enter
4. Tags are created automatically when first used

### Filter by Tags

- Use tag filter dropdown on Contacts page
- Select one or more tags
- List updates automatically

---

## Creating Campaigns

### Email Campaign Wizard (5 Steps)

**Step 1: Basic Info**
- Campaign name (internal use)
- Campaign type (select "Sales" for sales campaigns)

**Step 2: Email Content**
- Subject line (what recipients see)
- Preview text (appears in inbox preview)
- Email body (use rich text editor)
- Insert variables: `{{first_name}}`, `{{company}}`

**Step 3: Add Contacts**
- Search for contacts
- Filter by tags or lists
- Select contacts to add
- System automatically excludes:
  - Contacts on Do Not Contact (DNC) list
  - Contacts already in this campaign

**Step 4: Tracking**
- UTM parameters (optional)
- Custom tracking links

**Step 5: Schedule**
- Send now or schedule for later
- Review and confirm

### Campaign Status

- **Draft** - Being edited
- **Scheduled** - Queued to send
- **Sending** - Currently processing
- **Sent** - Completed
- **Paused** - Temporarily stopped

---

## User Settings

Access via user menu (bottom-left avatar):

### Account Tab
- Update name
- Change email
- Upload avatar

### Password Tab
- Change password
- Requires current password for security

### 2FA Tab
- Set up two-factor authentication (optional)
- Scan QR code with authenticator app
- Save backup codes

### Invites Tab
- Create invite links for new users
- View/revoke existing invites
- All users can invite (not just admins)

---

## Do Not Contact (DNC) List

Contacts marked as DNC will:
- **Not receive** any campaign emails
- Show "DNC" badge in contact list
- Be automatically excluded when adding contacts to campaigns

### Mark Contact as DNC

1. Open contact details
2. Toggle "Do Not Contact" switch
3. Contact immediately excluded from all campaigns

---

## Tips & Best Practices

### Organizing Contacts

- **Use Lists** for campaign targeting ("Q1 Leads", "Hot Prospects")
- **Use Tags** for attributes ("VIP", "Needs Follow-up", "Interested in X")
- One contact can be in multiple lists and have multiple tags

### Campaign Best Practices

- Test email with small group first
- Use personalization variables (`{{first_name}}`)
- Always include unsubscribe link (automated)
- Check DNC list is enforced
- Review preview before sending

### Data Hygiene

- Remove duplicate contacts regularly
- Keep contact info up to date
- Archive inactive contacts
- Export backups monthly

---

## Keyboard Shortcuts

- **Ctrl+K** (or Cmd+K) - Quick search
- **Esc** - Close dialogs
- **Tab** - Navigate forms

---

## Getting Help

### In-App Help
- Click "?" icon in top-right
- Search help articles
- View video tutorials (if available)

### Support
- Email: support@sarsonfunds.com
- Include screenshot if reporting a bug
- Describe what you expected vs. what happened

---

## Troubleshooting

### "I can't log in"
- Check password (case-sensitive)
- Clear browser cache
- Try different browser
- Contact admin to reset password

### "CSV import failed"
- Ensure CSV is UTF-8 encoded
- Check required columns present
- Remove special characters from data
- Try importing smaller batch (1000 rows)

### "Contacts not showing in campaign"
- Check if contact is on DNC list
- Check if contact already in campaign
- Verify list/tag filters applied correctly

### "Email not sending"
- Check campaign status (must be "Scheduled" or "Sending")
- Verify contacts added to campaign
- Check background services running (admin only)

---

## Admin Features

### User Management
- View all users
- Deactivate users
- Change user roles (admin/user)

### System Settings
- Configure email templates
- Set domain restrictions
- Adjust rate limits
- Review audit logs

### Audit Logs
- Track all user actions
- Filter by user, date, action type
- Export for compliance

---

## Privacy & Security

- Passwords are encrypted (never stored in plain text)
- All data encrypted in transit (HTTPS)
- Audit trail tracks all changes
- Contact data never leaves your server
- Regular backups recommended

---

**Version:** 1.0  
**Last Updated:** March 2026  
**For:** Sarson Funds CRM
