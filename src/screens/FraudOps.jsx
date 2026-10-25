import React, { useMemo, useState } from 'react';
import { api } from '../api.js';
import { usePoll } from '../hooks.js';
import { formatDurationWords, formatTime, pct } from '../format.js';
import { AuditTrail, ErrorBanner, HoldTimer, PaymentTable, VerdictCard } from '../components.jsx';

function median(xs) {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

function DetectorDetail({ v }) {
  if (!v || v.signed || v.model_version === 'seal-v1') return null;
  const n = (x, d = 2) => (x === null || x === undefined ? 'not measured' : Number(x).toFixed(d));
  return (
    <table className="kv">
      <tbody>
        <tr><th>Detector score</th><td>{n(v.score)} <span className="quiet">(0 = clean, 1 = manipulated)</span></td></tr>
        <tr><th>Pulse (BPM)</th><td>{n(v.bpm, 1)}</td></tr>
        <tr><th>Pulse signal quality (SNR)</th><td>{n(v.pulse_snr)}</td></tr>
        <tr><th>Forehead vs cheek pulse match</th><td>{n(v.region_correlation)}</td></tr>
        <tr><th>Face found in</th><td>{v.face_found_rate === undefined ? 'not measured' : pct(v.face_found_rate, 0)} of frames</td></tr>
        <tr><th>Check took</th><td>{n(v.processing_seconds, 1)} s · {v.model_version}</td></tr>
      </tbody>
    </table>
  );
}

export default function FraudOps({ metrics }) {
  const [selected, setSelected] = useState(null);
  const held = usePoll(() => api.payments('held'), 1500);
  const all = usePoll(() => api.payments(), 3000);
  const detail = usePoll(() => (selected ? api.payment(selected) : Promise.resolve(null)), 1500, [selected]);
  const [note, setNote] = useState('');
  const [msg, setMsg] = useState(null);
  const [report, setReport] = useState(null);

  const resolved = useMemo(() => (all.data || []).filter((p) => p.held_at && p.resolved_at), [all.data]);
  const cleared = resolved.filter((p) => p.status === 'RELEASED').map((p) => p.resolution_seconds).filter((x) => x !== null);

  const p = detail.data;
  const held_ = p && (p.status === 'HELD_CALLBACK' || p.status === 'HELD_SUSPICIOUS');
  const confirmed = p?.callback?.outcome === 'confirmed';

  async function act(fn) {
    setMsg(null);
    try { const r = await fn(); await detail.refresh(); return r; } catch (e) { setMsg(e.message); }
  }

  function select(id) { setSelected(id); setReport(null); setNote(''); setMsg(null); }

  function download() {
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `${report.report_id}.json`; a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <>
      <ErrorBanner error={held.error} offline={held.offline} />
      <div className="grid-2">
        <div className="stack">
          <section className="card">
            <h2>On hold</h2>
            {!held.data && !held.error && <div className="skeleton" />}
            {held.data && held.data.length === 0 && <p className="empty">Nothing on hold.</p>}
            {held.data && held.data.length > 0 && (
              <PaymentTable rows={held.data} selected={selected} onSelect={select} showHeld />
            )}
          </section>
          <section className="card">
            <h2>Resolved today</h2>
            {resolved.length === 0 && <p className="empty">None yet.</p>}
            {cleared.length > 0 && (
              <p>Genuine payments cleared by callback: median <b>{formatDurationWords(median(cleared))}</b> on hold ({cleared.length})</p>
            )}
            {resolved.length > 0 && (
              <PaymentTable rows={resolved} selected={selected} onSelect={select} showHeld />
            )}
          </section>
        </div>

        <div>
          {!p && <section className="card empty"><p>Select a held payment to see its evidence.</p></section>}
          {p && (
            <VerdictCard payment={p} metrics={metrics}>
              <p><HoldTimer payment={p} /></p>
              <DetectorDetail v={p.verdict} />
              {p.clip_sha256 && <p className="quiet small mono">Video fingerprint (SHA-256): {p.clip_sha256.slice(0, 16)}…</p>}

              {held_ && (
                <div className="callback">
                  <h3>Callback</h3>
                  <p>Call {p.approver_name} on his registered number {p.registered_phone_masked}. Not the number in the message.</p>
                  {p.callback
                    ? <p className={confirmed ? 'good-text' : 'danger-text'}>Approver {p.callback.outcome} at {formatTime(p.callback.at)}</p>
                    : (
                      <div className="actions">
                        <button onClick={() => act(() => api.callback(p.payment_id, 'confirmed'))}>Approver confirmed</button>
                        <button onClick={() => act(() => api.callback(p.payment_id, 'denied'))}>Approver denied</button>
                      </div>
                    )}
                </div>
              )}

              {held_ && (
                <div className="actions">
                  <button className="primary" disabled={!confirmed} title={confirmed ? '' : 'The approver must confirm on the callback first'}
                          onClick={() => act(() => api.release(p.payment_id))}>Release</button>
                  {!confirmed && <span className="quiet small">Release unlocks after the approver confirms.</span>}
                </div>
              )}
              {held_ && (
                <div className="reject">
                  <label htmlFor="note">Reject with a note</label>
                  <div className="actions">
                    <input id="note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Approver denied on callback" />
                    <button className="danger" onClick={() => act(() => api.reject(p.payment_id, note || 'Rejected by fraud ops'))}>Reject</button>
                  </div>
                </div>
              )}
              {p.status === 'REJECTED' && (
                <div className="actions">
                  <button onClick={async () => setReport(await act(() => api.report(p.payment_id)))}>Create report</button>
                  {report && <button onClick={download}>Download</button>}
                </div>
              )}
              {report && <pre className="report">{JSON.stringify(report, null, 2)}</pre>}
              {msg && <p className="danger-text">{msg}</p>}
              <AuditTrail audit={p.audit} />
            </VerdictCard>
          )}
        </div>
      </div>
    </>
  );
}
