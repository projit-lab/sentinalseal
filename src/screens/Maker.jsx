import React, { useEffect, useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { api } from '../api.js';
import { usePoll } from '../hooks.js';
import { formatINR } from '../format.js';
import { StatusBadge } from '../components.jsx';

const EMPTY = { payee_name: '', payee_account: '', amount_inr: '', approver_id: '', new_payee: true };

export default function Maker({ openInChecker }) {
  const [approvers, setApprovers] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [current, setCurrent] = useState(null); // payment_id just created
  const [mode, setMode] = useState(null); // 'seal' | 'upload'
  const [uploadMsg, setUploadMsg] = useState(null);
  const [demoMsg, setDemoMsg] = useState(null);

  useEffect(() => {
    api.approvers().then((a) => {
      setApprovers(a);
      setForm((f) => ({ ...f, approver_id: f.approver_id || (a.find((x) => x.enrolled) || a[0])?.approver_id || '' }));
    }).catch((e) => setError(e.message));
  }, []);

  const { data: payment } = usePoll(() => (current ? api.payment(current) : Promise.resolve(null)), 1500, [current]);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value });

  async function create(e) {
    e.preventDefault();
    setError(null); setUploadMsg(null); setDemoMsg(null); setMode(null);
    const amount = Number(form.amount_inr);
    if (!form.payee_name.trim()) return setError('Enter the payee name.');
    if (form.payee_account.replace(/\W/g, '').length < 4) return setError('Enter the payee account number.');
    if (!(amount > 0)) return setError('Enter an amount above ₹0.');
    setBusy(true);
    try {
      const p = await api.createPayment({ ...form, amount_inr: amount });
      setCurrent(p.payment_id);
    } catch (err) { setError(err.message); }
    setBusy(false);
  }

  async function upload(e) {
    const file = e.target.files?.[0];
    if (!file || !current) return;
    setUploadMsg('Uploading…');
    try {
      await api.uploadInstruction(current, file);
      setUploadMsg('Uploaded. The check is running; follow it in Payments to release.');
    } catch (err) { setUploadMsg(err.message); }
    e.target.value = '';
  }

  async function newQr() {
    try { await api.newApprovalSession(current); } catch (err) { setError(err.message); }
  }

  async function replay() {
    setDemoMsg('Replaying the last accepted seal on this payment…');
    try {
      const r = await api.replay(current);
      setDemoMsg(r.accepted ? 'Accepted (unexpected).' : `Refused: ${r.reason}`);
    } catch (err) { setDemoMsg(err.message); }
  }

  const p = payment;
  const approver = approvers.find((a) => a.approver_id === form.approver_id);

  return (
    <div className="grid-2">
      <form className="card" onSubmit={create} noValidate>
        <h2>New payment</h2>
        <label htmlFor="payee">Payee name</label>
        <input id="payee" value={form.payee_name} onChange={set('payee_name')} placeholder="Vendor Pvt Ltd" />
        <label htmlFor="acct">Payee account number</label>
        <input id="acct" value={form.payee_account} onChange={set('payee_account')} placeholder="50100234414417" inputMode="numeric" />
        <label htmlFor="amt">Amount (₹)</label>
        <input id="amt" value={form.amount_inr} onChange={set('amount_inr')} placeholder="4800000" inputMode="numeric" />
        {form.amount_inr && <p className="quiet small">{formatINR(Number(form.amount_inr))}</p>}
        <label htmlFor="appr">Approver</label>
        <select id="appr" value={form.approver_id} onChange={set('approver_id')}>
          {approvers.map((a) => (
            <option key={a.approver_id} value={a.approver_id}>
              {a.name} ({a.role}){a.enrolled ? '' : ' · phone not enrolled'}
            </option>
          ))}
        </select>
        <label className="check" htmlFor="newp">
          <input id="newp" type="checkbox" checked={form.new_payee} onChange={set('new_payee')} />
          New payee <span className="quiet small">(demo toggle; a real bank already knows this)</span>
        </label>
        {error && <p className="danger-text">{error}</p>}
        <button className="primary" disabled={busy}>{busy ? 'Creating…' : 'Create payment'}</button>
        {approver && !approver.enrolled && (
          <p className="quiet small">{approver.name}'s phone isn't enrolled yet, so sealed approval won't work until it is.</p>
        )}
      </form>

      <div className="stack">
        {!p && (
          <section className="card empty">
            <p>Create a payment to see whether it needs a check.</p>
            <p className="quiet small">Rule: new payee and ₹5,00,000 or more → sealed approval or instruction check.</p>
          </section>
        )}
        {p && (
          <section className="card">
            <header className="verdict-head">
              <StatusBadge status={p.status} />
              <span className="amount">{formatINR(p.amount_inr)}</span>
              <span className="quiet">to {p.payee_name} ({p.payee_account_masked}) · {p.payment_id}</span>
            </header>
            {!p.check_required && (
              <p className="headline">No extra check needed: existing payee or under {formatINR(p.threshold_inr)}. Sent to the checker.</p>
            )}
            {p.check_required && p.status === 'AWAITING_APPROVAL' && (
              <>
                <p className="headline">Approval required for {formatINR(p.amount_inr)} to a new payee.</p>
                <div className="choice">
                  <button type="button" className={mode === 'seal' ? 'primary' : ''} onClick={() => setMode('seal')}>
                    Request sealed approval
                  </button>
                  <button type="button" className={mode === 'upload' ? 'primary' : ''} onClick={() => setMode('upload')}>
                    Upload the instruction you received
                  </button>
                </div>
              </>
            )}
            {mode === 'seal' && p.status === 'AWAITING_APPROVAL' && (
              <div className="qr">
                <QRCodeSVG value={`sentinelseal:${p.payment_id}:${p.session_id}`} size={200} level="M" />
                <div>
                  <p>{p.approver_name} scans this with the SentinelSeal app, checks the payee and amount, and approves.</p>
                  <p className="quiet small">The code expires after 5 minutes.</p>
                  <button type="button" onClick={newQr}>New QR code</button>
                </div>
              </div>
            )}
            {mode === 'upload' && (p.status === 'AWAITING_APPROVAL') && (
              <div className="upload">
                <label htmlFor="instr">What instruction is this payment based on? (video)</label>
                <input id="instr" type="file" accept="video/*" onChange={upload} />
                <p className="quiet small">Video under 100 MB. It is deleted as soon as the check finishes.</p>
              </div>
            )}
            {uploadMsg && <p className="quiet">{uploadMsg}</p>}
            {p.status !== 'AWAITING_APPROVAL' && p.check_required && (
              <p className="quiet">Status: {p.status.replace('_', ' ').toLowerCase()}.</p>
            )}
            <button type="button" className="link" onClick={() => openInChecker(p.payment_id)}>Open in Payments to release →</button>

            <details className="demo">
              <summary>Demo tools (DEMO ONLY)</summary>
              <p className="quiet small">Resends the last accepted seal (from another payment) against this one, as an attacker would.</p>
              <button type="button" onClick={replay}>Replay last signature on this payment</button>
              {demoMsg && <p className="quiet small">{demoMsg}</p>}
            </details>
          </section>
        )}
      </div>
    </div>
  );
}
