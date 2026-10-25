import React from 'react';
import { api } from './api.js';
import { useNow } from './hooks.js';
import { formatDuration, formatDurationWords, formatINR, formatTime, pct, secondsSince } from './format.js';

// ── Status ───────────────────────────────────────────────────────────
export const STATUS = {
  NOT_REQUIRED: { label: 'No check needed', tone: 'neutral', icon: '–' },
  AWAITING_APPROVAL: { label: 'Awaiting seal', tone: 'neutral', icon: '…' },
  ANALYZING: { label: 'Checking video', tone: 'busy', icon: '◌' },
  VERIFIED: { label: 'Verified', tone: 'good', icon: '✓' },
  HELD_CALLBACK: { label: 'Needs callback', tone: 'warn', icon: '!' },
  HELD_SUSPICIOUS: { label: 'Suspicious', tone: 'bad', icon: '✕' },
  RELEASED: { label: 'Released', tone: 'done', icon: '✓' },
  REJECTED: { label: 'Rejected', tone: 'done', icon: '✕' },
};

export function StatusBadge({ status }) {
  const s = STATUS[status] || { label: status || '—', tone: 'neutral', icon: '' };
  return (
    <span className={`badge badge-${s.tone}`}>
      <span aria-hidden="true" className={s.tone === 'busy' ? 'spin' : ''}>{s.icon}</span> {s.label}
    </span>
  );
}

const HEADLINE = {
  VERIFIED: (p) => `Sealed by ${p.sealed_by}'s enrolled phone at ${formatTime(p.sealed_at)}.`,
  HELD_CALLBACK: () => 'Not sealed. Held until the approver confirms on his registered number.',
  HELD_SUSPICIOUS: () => 'Held. Strong signs this instruction is not genuine.',
  NOT_REQUIRED: (p) => `No extra check needed: existing payee or under ${formatINR(p.threshold_inr)}.`,
  AWAITING_APPROVAL: () => 'Waiting for the approver to seal this payment, or for the instruction it is based on.',
  ANALYZING: () => 'Checking the instruction video…',
};

export function ReasonList({ reasons }) {
  if (!reasons || !reasons.length) return null;
  return (
    <ul className="reasons">
      {reasons.map((r, i) => <li key={i}>{r}</li>)}
    </ul>
  );
}

export function FrameStrip({ payment }) {
  const frames = payment.thumbnails || [];
  if (!frames.length) return null;
  return (
    <div className="frames">
      {frames.map((n) => (
        <figure key={n}>
          <img src={api.frameUrl(payment.payment_id, n)} alt={`Flagged frame ${n}`} />
          <figcaption>Frame {n}</figcaption>
        </figure>
      ))}
    </div>
  );
}

export function ClipLine({ payment }) {
  if (payment.status === 'ANALYZING') {
    return <p className="quiet">Video is being checked; it will be deleted when the check finishes.</p>;
  }
  if (!payment.analysis_started_at) return null;
  if (!payment.raw_clip_deleted_at) {
    return <p className="danger-text">Raw video not deleted.</p>;
  }
  return (
    <p className="quiet">
      Raw video deleted at {formatTime(payment.raw_clip_deleted_at)} · kept: flagged frames and the file's fingerprint
    </p>
  );
}

export function FprLine({ metrics }) {
  const s = metrics && metrics.measured ? metrics.suites?.accuracy_deepspeak : null;
  if (!s || s.fpr === undefined) return null;
  return (
    <p className="quiet">
      On our test set, this check wrongly held {pct(s.fpr)} of {s.n_real ?? '—'} genuine videos the models never saw.
    </p>
  );
}

export function Elapsed({ since, label }) {
  const now = useNow();
  return <span className="mono">{label} {formatDuration(secondsSince(since, now))}</span>;
}

export function HoldTimer({ payment }) {
  const now = useNow();
  if (!payment.held_at) return null;
  if (payment.resolved_at) {
    const how = payment.status === 'RELEASED'
      ? (payment.callback?.outcome === 'confirmed' ? 'cleared by callback' : 'released')
      : payment.status === 'VERIFIED' ? 'sealed by approver' : 'rejected';
    return (
      <span className="mono">
        Held at {formatTime(payment.held_at)} → {formatTime(payment.resolved_at)} · {formatDurationWords(payment.resolution_seconds)} · {how}
      </span>
    );
  }
  return <span className="mono">Held for {formatDuration(secondsSince(payment.held_at, now))}</span>;
}

export function VerdictCard({ payment, metrics, children }) {
  const v = payment.verdict || {};
  const headline = (HEADLINE[payment.status] || (() => null))(payment);
  const held = payment.status === 'HELD_CALLBACK' || payment.status === 'HELD_SUSPICIOUS';
  return (
    <section className={`card verdict tone-${(STATUS[payment.status] || {}).tone || 'neutral'}`}>
      <header className="verdict-head">
        <StatusBadge status={payment.status} />
        <span className="amount">{formatINR(payment.amount_inr)}</span>
        <span className="quiet">to {payment.payee_name} ({payment.payee_account_masked})</span>
      </header>
      {headline && <p className="headline">{headline}</p>}
      {payment.status === 'ANALYZING' && <Elapsed since={payment.analysis_started_at} label="Elapsed" />}
      {(payment.status === 'RELEASED' || payment.status === 'REJECTED') && v.verdict && (
        <p className="quiet">Check result: {v.verdict.replace('_', ' ').toLowerCase()}</p>
      )}
      <ReasonList reasons={v.reasons} />
      <FrameStrip payment={payment} />
      <ClipLine payment={payment} />
      {held && <FprLine metrics={metrics} />}
      {held && <p className="quiet">A person reviews every held payment. Nothing is rejected automatically.</p>}
      {children}
    </section>
  );
}

export function PaymentTable({ rows, selected, onSelect, showHeld }) {
  return (
    <div className="table-wrap">
      <table className="ptable">
        <thead>
          <tr>
            <th>Status</th><th>Payee</th><th className="num">Amount</th>
            <th>{showHeld ? 'Held' : 'Created'}</th><th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.payment_id} className={p.payment_id === selected ? 'sel' : ''}
                onClick={() => onSelect(p.payment_id)} tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && onSelect(p.payment_id)}>
              <td><StatusBadge status={p.status} /></td>
              <td>{p.payee_name}<div className="quiet small">{p.payment_id}</div></td>
              <td className="num">{formatINR(p.amount_inr)}</td>
              <td className="mono">{showHeld ? <HoldTimer payment={p} /> : formatTime(p.created_at)}</td>
              <td className="small">{p.first_reason || ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AuditTrail({ audit }) {
  if (!audit || !audit.length) return null;
  return (
    <details className="audit">
      <summary>Audit trail ({audit.length})</summary>
      <ol>
        {audit.map((a, i) => (
          <li key={i}>
            <span className="mono">{formatTime(a.at)}</span> · <b>{a.actor}</b> · {a.action}
            {a.note ? <span className="quiet"> · {a.note}</span> : null}
          </li>
        ))}
      </ol>
    </details>
  );
}

export function ErrorBanner({ error, offline }) {
  if (!error) return null;
  return (
    <div className="banner" role="alert">
      {offline ? "Can't reach the server. Showing the last data; retrying every 5 s." : error.message}
    </div>
  );
}
