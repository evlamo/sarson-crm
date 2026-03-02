import api from './api';

export interface AuditLogEntry {
  id: string;
  user_id: string | null;
  user_name: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  old_values: Record<string, unknown> | null;
  new_values: Record<string, unknown> | null;
  created_at: string;
}

export interface FieldHistoryEntry {
  id: string;
  contact_id: string;
  field_name: string;
  old_value: string | null;
  new_value: string | null;
  changed_by: string | null;
  changed_by_name: string | null;
  changed_at: string;
  source: string;
}

export interface PaginatedAuditLogs {
  data: AuditLogEntry[];
  total: number;
  page: number;
  per_page: number;
}

export interface PaginatedFieldHistory {
  data: FieldHistoryEntry[];
  total: number;
  page: number;
  per_page: number;
}

export async function fetchAuditLogs(params?: {
  entity_type?: string;
  entity_id?: string;
  action?: string;
  page?: number;
  per_page?: number;
}): Promise<PaginatedAuditLogs> {
  const res = await api.get<PaginatedAuditLogs>('/audit', { params });
  return res.data;
}

export async function fetchContactAuditLogs(
  contactId: string,
  page = 1,
  perPage = 50
): Promise<PaginatedAuditLogs> {
  const res = await api.get<PaginatedAuditLogs>(`/audit/contacts/${contactId}`, {
    params: { page, per_page: perPage },
  });
  return res.data;
}

export async function fetchContactFieldHistory(
  contactId: string,
  fieldName?: string,
  page = 1,
  perPage = 50
): Promise<PaginatedFieldHistory> {
  const res = await api.get<PaginatedFieldHistory>(`/audit/contacts/${contactId}/field-history`, {
    params: { field_name: fieldName, page, per_page: perPage },
  });
  return res.data;
}

export async function revertContactField(
  contactId: string,
  fieldName: string,
  targetValue: string | null
): Promise<{ status: string; field: string; old_value: string | null; new_value: string | null }> {
  const res = await api.post(`/audit/contacts/${contactId}/revert-field`, {
    field_name: fieldName,
    target_value: targetValue,
  });
  return res.data;
}
