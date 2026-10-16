import { z } from 'zod';
export const pointSchema = z.object({ lat: z.number().finite().min(6).max(38), lng: z.number().finite().min(68).max(98) }).strict();
export const placeSearchSchema = z.object({ query: z.string().trim().min(2, 'Enter at least two characters.').max(160, 'Use a shorter place or address.').refine(v => !/[\u0000-\u001f\u007f]/u.test(v), 'Use a place name or address.') }).strict();
export const searchSchema = z.object({
  destination: pointSchema, origin: pointSchema.optional(),
  radius: z.number().int().min(100).max(2500).default(1000),
  arrivalAt: z.string().datetime({ offset: true }), durationMinutes: z.number().int().min(30).max(1440).default(120),
  vehicle: z.enum(['CAR', 'TWO_WHEELER']).default('CAR'),
  requirements: z.array(z.enum(['EV_CHARGING', 'ACCESSIBLE_PARKING'])).max(2).default([]),
  type: z.enum(['all', 'underground', 'surface', 'street_side']).default('all'),
  sort: z.enum(['distance', 'price']).default('distance'), includeUnknown: z.boolean().default(true), includeCustomer: z.boolean().default(false),
}).strict();
export const reportSchema = z.object({ facilityId: z.string().regex(/^[a-z0-9-]{1,60}$/), category: z.enum(['FOUND_SPACE', 'FULL', 'CLOSED', 'DETAILS_WRONG']), observedAt: z.string().datetime({ offset: true }) }).strict();
export const observationSchema = z.object({ state: z.enum(['AVAILABLE', 'LIMITED', 'FULL', 'UNKNOWN']), observedAt: z.string().datetime({ offset: true }) }).strict();
export const sourceUrlSchema = z.string().url().max(500).refine(v => { const u = new URL(v); return u.protocol === 'https:' && !u.username && !u.password; }, 'Use a public HTTPS source URL');
export const listingSchema = z.object({
  name: z.string().trim().min(3).max(100), access: z.enum(['PUBLIC','CUSTOMERS_ONLY','PRIVATE','PERMIT','UNKNOWN']),
  type: z.enum(['underground','surface','street_side']), entryNotes: z.string().trim().max(500),
  active: z.boolean(), vehicles: z.array(z.enum(['CAR','TWO_WHEELER'])).max(2),
  features: z.array(z.enum(['EV_CHARGING','ACCESSIBLE_PARKING'])).max(2),
  rate: z.object({ amount: z.number().min(0).max(10000), unit: z.enum(['PER_HOUR','PER_ENTRY','PER_DAY']), currency: z.literal('INR') }).nullable(),
  hours: z.array(z.object({ day: z.number().int().min(0).max(6), opens: z.number().int().min(0).max(1439), closes: z.number().int().min(0).max(1440), overnight: z.boolean(), closed: z.boolean() }).refine(h => h.closed || (h.overnight ? h.closes <= h.opens : h.closes > h.opens), 'Hours must describe a valid interval')).max(14).nullable(),
  sourceName: z.string().trim().min(3).max(100), sourceUrl: sourceUrlSchema,
  version: z.number().int().min(1),
}).strict();
export const memberSchema = z.object({ userId: z.string().min(3).max(200), displayName: z.string().trim().min(2).max(80), role: z.enum(['OPERATOR','REVIEWER']), facilityIds: z.array(z.string().regex(/^[a-z0-9-]{1,60}$/)).max(30) }).strict();
export const importSchema=z.object({name:z.string().trim().min(3).max(100),point:pointSchema,type:z.enum(['surface','underground','street_side']),access:z.enum(['PUBLIC','CUSTOMERS_ONLY','PRIVATE','PERMIT','UNKNOWN']),sourceName:z.string().trim().min(3).max(100),sourceUrl:sourceUrlSchema,license:z.enum(['ODbL-1.0','First-party permission']),entryNotes:z.string().trim().max(500)}).strict();
export class ApiError extends Error { status: number; code: string; constructor(status: number, code: string, message: string) { super(message); this.status=status; this.code=code; } }
export async function readBody<T extends z.ZodTypeAny>(request: Request, schema: T, maxBytes = 8192): Promise<z.output<T>> {
  if (!request.headers.get('content-type')?.startsWith('application/json')) throw new ApiError(415,'CONTENT_TYPE','Send JSON data.');
  if (Number(request.headers.get('content-length')) > maxBytes) throw new ApiError(413,'TOO_LARGE','Request is too large.');
  const reader = request.body?.getReader(); let bytes = 0; const chunks: Uint8Array[] = [];
  if (reader) while (true) { const { done, value } = await reader.read(); if (done) break; bytes += value.byteLength; if (bytes > maxBytes) { await reader.cancel(); throw new ApiError(413,'TOO_LARGE','Request is too large.'); } chunks.push(value); }
  const all = new Uint8Array(bytes); let off=0; for (const c of chunks) { all.set(c,off); off+=c.length; }
  let parsed: unknown; try { parsed = JSON.parse(new TextDecoder().decode(all)); } catch { throw new ApiError(400,'INVALID_JSON','Please send valid JSON.'); }
  const result = schema.safeParse(parsed); if (!result.success) throw new ApiError(400,'INVALID_INPUT',result.error.issues[0]?.message ?? 'Check the submitted details.');
  return result.data;
}
export function requireSameOrigin(request: Request) {
  const origin = request.headers.get('origin');
  if (!origin || origin !== new URL(request.url).origin) throw new ApiError(403,'ORIGIN','This action must be sent from ParkMyCar.');
}
export function requireRecent(time: string, now = Date.now(), ageMinutes = 30) {
  const t=Date.parse(time); if (!Number.isFinite(t) || t > now + 30000 || t < now - ageMinutes * 60000) throw new ApiError(400,'OBSERVATION_TIME',`Use an observation from the last ${ageMinutes} minutes.`);
}
