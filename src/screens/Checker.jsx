import React, { useState } from 'react';
import { api } from '../api.js';
import { usePoll } from '../hooks.js';
import { ErrorBanner, PaymentTable, VerdictCard } from '../components.jsx';

export default function Checker({ selected, setSelected, metrics }) {
  const list = usePoll(() => api.payments(), 1500);
  const detail = usePoll(() => (selected ? api.payment(selected) : Promise.resolve(null)), 1500, [selected]);
  const [msg, setMsg] = useState(null);

  async function release() {
    setMsg(null);
    try { await api.release(selected); await detail.refresh(); } catch (e) { setMsg(e.message); }
  }

  const rows = list.data || [];
  const p = detail.data;

  return (
    <>
      <ErrorBanner error={list.error} offline={list.offline} />
      <div className="grid-2">
        <section className="card">
          <h2>Payments to release</h2>
          {!list.data && !list.error && <div className="skeleton" />}
          {list.data && rows.length === 0 && <p className="empty">No payments waiting. Create one in New payment.</p>}
          {rows.length > 0 && <PaymentTable rows={rows} selected={selected} onSelect={setSelected} />}
        </section>
        <div>
          {!p && <section className="card empty"><p>Select a payment to see its check.</p></section>}
          {p && (
            <VerdictCard payment={p} metrics={metrics}>
              <div className="actions">
                {(p.status === 'VERIFIED' || p.status === 'NOT_REQUIRED') && (
                  <button className="primary" onClick={release}>Release payment</button>
                )}
                {p.status === 'HELD_CALLBACK' && <span className="held-note">Held: waiting for callback</span>}
                {p.status === 'HELD_SUSPICIOUS' && <span className="held-note">Held: with fraud team</span>}
                {p.status === 'AWAITING_APPROVAL' && <span className="held-note">Waiting for seal or instruction check</span>}
                {(p.status === 'RELEASED' || p.status === 'REJECTED') && (
                  <span className="quiet">{p.status === 'RELEASED' ? 'Released' : 'Rejected'} · {(p.audit || []).slice(-1)[0]?.actor}</span>
                )}
              </div>
              {msg && <p className="danger-text">{msg}</p>}
            </VerdictCard>
          )}
        </div>
      </div>
    </>
  );
}
