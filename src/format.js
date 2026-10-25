// ₹48,00,000 (Indian digit grouping)
export function formatINR(amount) {
  if (amount === null || amount === undefined || Number.isNaN(Number(amount))) return '—';
  return '₹' + Math.round(Number(amount)).toLocaleString('en-IN');
}

export function formatTime(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
}

export function formatDuration(seconds) {
  if (seconds === null || seconds === undefined) return '—';
  const s = Math.max(0, Math.round(seconds));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${String(r).padStart(2, '0')}`;
}

export function formatDurationWords(seconds) {
  if (seconds === null || seconds === undefined) return '—';
  const s = Math.max(0, Math.round(seconds));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return m ? `${m} min ${r} s` : `${r} s`;
}

export function secondsSince(iso, now = Date.now()) {
  return iso ? (now - new Date(iso).getTime()) / 1000 : null;
}

export function pct(x, digits = 1) {
  return x === null || x === undefined ? '—' : `${(x * 100).toFixed(digits)}%`;
}
