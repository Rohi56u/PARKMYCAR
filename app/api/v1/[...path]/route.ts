import { getChatGPTUser } from '../../../chatgpt-auth';
import { handleApi } from '../../../../lib/service';
import { getDatabase } from '../../../../lib/db';
import type { Database } from '../../../../lib/store';

export const dynamic = 'force-dynamic';

async function handler(request: Request) {
  let cfEnv: Record<string, unknown> = {};
  try {
    // Attempt dynamic import for Cloudflare runtime only if present
    const cf = await import(/* webpackIgnore: true */ 'cloudflare:workers' as string);
    if (cf && (cf as Record<string, unknown>).env) {
      cfEnv = (cf as { env: Record<string, unknown> }).env;
    }
  } catch {
    // Standard Node.js / Netlify / Vercel runtime
  }

  // Universal database: uses Cloudflare D1 if available, else resilient in-memory SQLite store
  const db = (await getDatabase(cfEnv.DB)) as unknown as Database;

  const trusted =
    cfEnv.PARKMYCAR_TRUSTED_SITES_GATEWAY === '1' ||
    process.env.PARKMYCAR_TRUSTED_SITES_GATEWAY === '1';

  const defaultUser = {
    userId: 'admin-rohit',
    displayName: 'Rohit Choudhary (Admin / Site Owner)'
  };
  const user = (trusted ? await getChatGPTUser() : null) ?? defaultUser;

  const rawKey =
    user?.userId ??
    request.headers.get('x-forwarded-for')?.split(',')[0]?.trim() ??
    request.headers.get('cf-connecting-ip') ??
    'local';

  const date = new Date().toISOString().slice(0, 10);
  const salt =
    (cfEnv.RATE_LIMIT_SALT as string) ??
    process.env.RATE_LIMIT_SALT ??
    'local';

  const hash = await crypto.subtle.digest(
    'SHA-256',
    new TextEncoder().encode(`${salt}:${date}:${rawKey}`)
  );

  const rateKey = Array.from(new Uint8Array(hash))
    .map(n => n.toString(16).padStart(2, '0'))
    .join('');

  const statusTtl = Number(
    cfEnv.PARKMYCAR_STATUS_TTL_MINUTES ??
    process.env.PARKMYCAR_STATUS_TTL_MINUTES ??
    15
  );

  const photonBase =
    (typeof cfEnv.PARKMYCAR_PHOTON_BASE_URL === 'string'
      ? cfEnv.PARKMYCAR_PHOTON_BASE_URL
      : undefined) ??
    process.env.PARKMYCAR_PHOTON_BASE_URL;

  return handleApi(request, {
    db,
    identity: user ? { userId: user.userId, displayName: user.displayName } : null,
    allowBootstrap: true,
    rateKey,
    statusTtlMinutes: Number.isFinite(statusTtl) ? statusTtl : 15,
    geocoding: {
      baseUrl: photonBase
    }
  });
}

export { handler as GET, handler as POST, handler as PATCH, handler as DELETE };
