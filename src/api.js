// One place for the backend address. Override with VITE_API_BASE in a .env file,
// e.g. VITE_API_BASE=http://192.168.1.20:8000/api/v1
export const API_BASE =
  import.meta.env.VITE_API_BASE ||
  `${window.location.protocol}//${window.location.hostname}:8000/api/v1`;

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options);
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!res.ok) {
    const detail = data && typeof data === 'object' ? data.detail : data;
    const msg = Array.isArray(detail) ? detail.map((d) => d.msg).join('; ') : detail;
    throw new Error(msg || `Request failed (${res.status})`);
  }
  return data;
}

const json = (method, body) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: body === undefined ? undefined : JSON.stringify(body),
});

export const api = {
  approvers: () => request('/approvers'),
  createPayment: (body) => request('/payments', json('POST', body)),
  payments: (status) => request(`/payments${status ? `?status=${status}` : ''}`),
  payment: (id) => request(`/payments/${id}`),
  newApprovalSession: (id) => request(`/payments/${id}/approval-session`, json('POST')),
  uploadInstruction: (id, file) => {
    const form = new FormData();
    form.append('file', file);
    return request(`/payments/${id}/instruction`, { method: 'POST', body: form });
  },
  frameUrl: (id, n) => `${API_BASE}/payments/${id}/frames/${n}`,
  callback: (id, outcome, note) => request(`/payments/${id}/callback`, json('POST', { outcome, note })),
  release: (id) => request(`/payments/${id}/release`, json('POST')),
  reject: (id, note) => request(`/payments/${id}/reject`, json('POST', { note })),
  report: (id) => request(`/payments/${id}/report`, json('POST')),
  metrics: () => request('/metrics'),
  misses: () => request('/metrics/misses'),
  replay: (targetId) => request('/demo/replay', json('POST', { target_payment_id: targetId })),
  health: () => request('/health'),
};
