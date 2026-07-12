import { useState } from 'react';
import { Sidebar } from './components/Sidebar/Sidebar';
import type { AppRoute } from './types';

export function App() {
  const [activeRoute, setActiveRoute] = useState<AppRoute>('dashboard');

  return (
    <div style={{ display: 'flex', height: '100vh', background: '#0d0f14' }}>
      <Sidebar activeRoute={activeRoute} onNavigate={setActiveRoute} />
      <main>{/* route content */}</main>
    </div>
  );
}