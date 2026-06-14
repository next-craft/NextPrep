// Mirrors the DB CHECK on reports.reason (Spec 03 — content policy).
// Keep values in sync with backend/app/models/report.py and the migration.
export const REPORT_REASONS = [
  { value: 'PIRACY', label: 'Pirated scan, photocopy, or unauthorized PDF' },
  { value: 'CONTACT_INFO', label: 'Phone/email/social handle in the listing' },
  { value: 'SPAM', label: 'Spam, duplicate, or misleading' },
  { value: 'NOT_STUDY_MATERIAL', label: 'Not study material' },
  { value: 'PROHIBITED', label: 'Other prohibited content' },
  { value: 'ABUSIVE', label: 'Abusive, harassing, or illegal' },
  { value: 'OTHER', label: 'Something else' },
]
