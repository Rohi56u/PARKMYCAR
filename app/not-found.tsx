import Link from 'next/link';

export const metadata = {
  title: '404: Page Not Found · ParkMyCar',
  description: 'The requested parking page or route does not exist.',
};

export default function NotFound() {
  return (
    <main style={{ minHeight: '70vh', display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: '24px' }}>
      <div>
        <h1 style={{ fontSize: '28px', fontWeight: 700, margin: '0 0 12px' }}>404 · Page Not Found</h1>
        <p style={{ color: '#47554d', fontSize: '14px', marginBottom: '20px' }}>The requested parking record or route does not exist.</p>
        <Link href="/" className="button button-dark">Back to Home</Link>
      </div>
    </main>
  );
}
