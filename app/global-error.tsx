'use client';

export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <head>
        <title>Error · ParkMyCar</title>
      </head>
      <body>
        <main style={{ minHeight: '70vh', display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: '24px' }}>
          <div>
            <h1 style={{ fontSize: '28px', fontWeight: 700, margin: '0 0 12px' }}>Something went wrong</h1>
            <p style={{ color: '#47554d', fontSize: '14px', marginBottom: '20px' }}>An unexpected error occurred while loading parking data.</p>
            <button className="button button-dark" onClick={() => reset()}>Try again</button>
          </div>
        </main>
      </body>
    </html>
  );
}
