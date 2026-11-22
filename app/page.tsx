'use client';
import dynamic from 'next/dynamic';

const ParkApp = dynamic(() => import('../components/ParkApp'), {
  ssr: false,
  loading: () => (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f8fafc', color: '#0f172a', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ width: 42, height: 42, border: '3.5px solid #e2e8f0', borderTopColor: '#10b981', borderRadius: '50%', animation: 'spin 0.75s linear infinite', margin: '0 auto 16px' }} />
        <h2 style={{ fontSize: 17, fontWeight: 700, margin: 0, letterSpacing: '-0.3px' }}>ParkMyCar Enterprise</h2>
        <p style={{ fontSize: 13, color: '#47554d', marginTop: 4 }}>Loading AI ANPR Camera &amp; Live Occupancy System…</p>
      </div>
    </div>
  ),
});

export default function Page() {
  return <ParkApp />;
}

