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
          <span className="seal" aria-hidden="true">◆</span> SentinelSeal
        </div>
        <nav aria-label="Screens">
          {SCREENS.map((s) => (
            <button key={s.id} className={s.id === screen ? 'tab active' : 'tab'} onClick={() => setScreen(s.id)}>
              {s.label}
            </button>
          ))}
        </nav>
        <div className={`server ${health.data ? 'ok' : 'down'}`} title={health.data ? 'Server reachable' : "Can't reach the server"}>
          <span className="dot" /> {health.data ? 'Server' : 'Offline'}
        </div>
      </header>
      {current.mock && (
        <div className="mock-label">Mock bank: stands in for the bank's existing corporate net banking. SentinelSeal plugs in behind it.</div>
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
