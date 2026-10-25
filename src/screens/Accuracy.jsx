import React, { useEffect, useState } from 'react';
import { api } from '../api.js';
import { pct } from '../format.js';

const ROBUST = [
  ['whatsapp_bitrate', 'WhatsApp-like compression'],
  ['360p', 'Downscaled to 360p'],
  ['dark_gamma', 'Darker video'],
  ['blur', 'Blur'],
  ['15fps', '15 frames per second'],
];
const ABLATION = [
  ['classifier_only', 'Pretrained classifiers only'],
  ['classifier_pulse', '+ pulse signal quality'],
  ['full_fusion', '+ forehead/cheek pulse match (full fusion)'],
];

const nm = (x, f = pct) => (x === null || x === undefined ? 'not measured' : f(x));

function Tile({ label, value, sub, big }) {
  return (
    <div className={`tile${big ? ' big' : ''}`}>
      <div className="tile-label">{label}</div>
      <div className="tile-value">{value}</div>
      {sub && <div className="quiet small">{sub}</div>}
    </div>
  );
}

function Suite({ title, s }) {
  if (!s) return <p className="quiet">{title}: not measured.</p>;
  const ci = s.bootstrap_ci_95;
  return (
    <>
      <div className="tiles">
        <Tile big label="False-positive rate (genuine videos held)" value={nm(s.fpr)} sub={`${s.n_real ?? '—'} genuine videos`} />
        <Tile label="False-negative rate (fakes missed)" value={nm(s.fnr)} sub={`${s.n_fake ?? '—'} fakes`} />
        <Tile label="Balanced accuracy" value={nm(s.balanced_accuracy)} sub={ci ? `95% interval ${pct(ci[0])}–${pct(ci[1])}` : null} />
        <Tile label="AUC" value={nm(s.auc, (x) => x.toFixed(3))} />
      </div>
      {s.confusion_matrix && (
        <table className="kv cm">
          <thead><tr><th /><th>Predicted genuine</th><th>Predicted fake</th></tr></thead>
          <tbody>
            <tr><th>Actually genuine</th><td>{s.confusion_matrix[0][0]}</td><td>{s.confusion_matrix[0][1]}</td></tr>
            <tr><th>Actually fake</th><td>{s.confusion_matrix[1][0]}</td><td>{s.confusion_matrix[1][1]}</td></tr>
          </tbody>
        </table>
      )}
    </>
  );
}

export default function Accuracy() {
  const [m, setM] = useState(null);
  const [misses, setMisses] = useState([]);
  const [error, setError] = useState(null);

  async function load() {
    setError(null);
    try {
      setM(await api.metrics());
      setMisses(await api.misses());
    } catch (e) { setError(e.message); }
  }
  useEffect(() => { load(); }, []);

  if (error) return <section className="card"><p className="danger-text">{error}</p><button onClick={load}>Retry</button></section>;
  if (!m) return <section className="card"><div className="skeleton" /></section>;

  const S = m.suites || {};
  return (
    <div className="stack">
      <section className="card">
        <div className="row-between">
          <h2>Measured accuracy</h2>
          <button onClick={load}>Reload results</button>
        </div>
        {!m.measured && (
          <div className="empty">
            <p><b>Not measured yet.</b> {m.reason}</p>
            <p className="quiet small">Numbers appear here only when results/metrics.json comes from running the detector on real test videos.</p>
          </div>
        )}
        {m.measured && (
          <p className="quiet small">Run {m.run_id} · seed {m.seed} · {m.hardware}</p>
        )}
      </section>

      {m.measured && (
        <>
          <section className="card">
            <h3>Main test set (DeepSpeak v1, never trained on)</h3>
            <Suite title="Main test set" s={S.accuracy_deepspeak} />
            {S.accuracy_deepspeak?.by_fake_type && (
              <table className="kv">
                <thead><tr><th>Fake type</th><th>Balanced accuracy</th><th>Missed</th></tr></thead>
                <tbody>
                  {Object.entries(S.accuracy_deepspeak.by_fake_type).map(([k, v]) => (
                    <tr key={k}><th>{k.replace('_', '-')}</th><td>{nm(v.balanced_accuracy)}</td><td>{nm(v.fnr)}</td></tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
          <section className="card">
            <h3>Cross-dataset (fit on DFDC, tested on DeepSpeak)</h3>
            <Suite title="Cross-dataset" s={S.cross_dataset} />
          </section>
          <section className="card grid-2 plain">
            <div>
              <h3>What each part adds (ablation)</h3>
              <table className="kv">
                <thead><tr><th>Pipeline</th><th>Balanced accuracy</th><th>AUC</th></tr></thead>
                <tbody>
                  {ABLATION.map(([k, label]) => (
                    <tr key={k}><th>{label}</th><td>{nm(S.ablation?.[k]?.balanced_accuracy)}</td><td>{nm(S.ablation?.[k]?.auc, (x) => x.toFixed(3))}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div>
              <h3>Robustness</h3>
              <table className="kv">
                <thead><tr><th>Condition</th><th>Balanced accuracy</th></tr></thead>
                <tbody>
                  {ROBUST.map(([k, label]) => (
                    <tr key={k}><th>{label}</th><td>{nm(S.robustness?.[k]?.balanced_accuracy)}</td></tr>
                  ))}
                </tbody>
              </table>
              <h3>Speed</h3>
              <p>Median {nm(S.latency?.median_seconds, (x) => `${x.toFixed(2)} s`)} · 95th percentile {nm(S.latency?.p95_seconds, (x) => `${x.toFixed(2)} s`)} per video</p>
            </div>
          </section>
          <section className="card">
            <h3>Failure cases</h3>
            {misses.length === 0 && <p className="quiet">No failure list in results/misses.json.</p>}
            {misses.length > 0 && (
              <table className="kv">
                <thead><tr><th>File</th><th>Truth</th><th>Our verdict</th><th>Why</th></tr></thead>
                <tbody>
                  {misses.map((x, i) => (
                    <tr key={i}><td className="mono small">{x.file}</td><td>{x.true_label}</td><td>{x.verdict}</td><td className="small">{x.reason}</td></tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}

      <section className="card">
        <h3>Reproduce these numbers</h3>
        <pre>{`git clone https://github.com/projit-lab/sentinalseal && cd sentinalseal
pip install -r eval/requirements.txt
python eval/get_data.py
python eval/run_all.py --seed 42
pytest backend/tests detector/tests`}</pre>
      </section>
    </div>
  );
}
