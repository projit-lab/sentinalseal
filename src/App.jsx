import React, { useState } from 'react';
import { api } from './api.js';
import { usePoll } from './hooks.js';
import Maker from './screens/Maker.jsx';
import Checker from './screens/Checker.jsx';
import FraudOps from './screens/FraudOps.jsx';
import Accuracy from './screens/Accuracy.jsx';

const SCREENS = [
  { id: 'maker', label: 'New payment', mock: true },
  { id: 'checker', label: 'Payments to release', mock: true },
  { id: 'fraud', label: 'Fraud-ops', mock: false },
  { id: 'accuracy', label: 'Accuracy', mock: false },
];

function initialScreen() {
  const h = window.location.hash.replace('#', '');
  return SCREENS.some((s) => s.id === h) ? h : 'maker';
}

export default function App() {
  const [screen, setScreenState] = useState(initialScreen);
  const [selected, setSelected] = useState(null);
  const health = usePoll(() => api.health(), 5000);
  const metrics = usePoll(() => api.metrics(), 30000);

  function setScreen(id) {
    setScreenState(id);
    window.location.hash = id;
  }

  const current = SCREENS.find((s) => s.id === screen);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <svg className="mark" viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="12" cy="12" r="10.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
            <circle cx="12" cy="12" r="6.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
            <path d="M9.2 12.2l1.9 1.9 3.8-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="wordmark">SentinelSeal</span>
          <span className="brand-sub">Payment approval verification</span>
        </div>
        <nav aria-label="Screens">
          {SCREENS.map((s) => (
            <button key={s.id} className={s.id === screen ? 'tab active' : 'tab'} onClick={() => setScreen(s.id)}>
              {s.label}
            </button>
          ))}
        </nav>
        <div className={`server ${health.data ? 'ok' : 'down'}`} title={health.data ? 'Server reachable' : "Can't reach the server"}>
          <span className="dot" /> {health.data ? 'Connected' : 'Offline'}
        </div>
      </header>
      {current.mock && (
        <div className="mock-label"><span className="mock-tag">Demo bank</span> These two screens stand in for the bank's existing corporate net banking. SentinelSeal runs behind them.</div>
      )}
      <main>
        {screen === 'maker' && (
          <Maker openInChecker={(id) => { setSelected(id); setScreen('checker'); }} />
        )}
        {screen === 'checker' && <Checker selected={selected} setSelected={setSelected} metrics={metrics.data} />}
        {screen === 'fraud' && <FraudOps metrics={metrics.data} />}
        {screen === 'accuracy' && <Accuracy />}
      </main>
    </div>
  );
}
