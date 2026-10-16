export type Point = { lat: number; lng: number };
export type Access = 'PUBLIC' | 'CUSTOMERS_ONLY' | 'PRIVATE' | 'PERMIT' | 'UNKNOWN';
export type Vehicle = 'CAR' | 'TWO_WHEELER';
export type EvidenceClass = 'STATIC_LISTING' | 'OPERATOR_REPORTED' | 'COMMUNITY_REPORTED';
export type ParkingState = 'AVAILABLE' | 'LIMITED' | 'FULL' | 'UNKNOWN';
export type Source = { name: string; url: string; fields: string[]; checkedAt: string; license: string };
export type Hours = { day: number; opens: number; closes: number; overnight: boolean; closed: boolean };
export type Rate = { amount: number; unit: 'PER_HOUR' | 'PER_ENTRY' | 'PER_DAY'; currency: 'INR'; source: string; checkedAt: string };
export type Facility = {
  id: string; name: string; area: string; nameKind: 'official' | 'area_label';
  point: Point; type: 'underground' | 'surface' | 'street_side'; access: Access;
  locationKind: 'area_centroid' | 'verified_entrance'; vehicles: Vehicle[];
  features: string[]; hours: Hours[] | null; rate: Rate | null;
  entryNotes: string; active: boolean; verification: 'MAPPED' | 'REVIEWED';
  sources: Source[]; version: number; operatorId: string | null;
};
export type Observation = {
  id: string; facilityId: string; state: ParkingState;
  evidenceClass: Exclude<EvidenceClass, 'STATIC_LISTING'>;
  source: string; observedAt: string; expiresAt: string;
};
export type Evidence = {
  state: ParkingState; evidenceClass: EvidenceClass; label: string; source: string | null;
  observedAt: string | null; expiresAt: string | null; conflict: boolean;
};
export type SearchInput = {
  destination: Point; origin?: Point; radius: number; arrivalAt: string;
  durationMinutes: number; vehicle: Vehicle; requirements: string[];
  type: 'all' | Facility['type']; sort: 'distance' | 'price';
  includeUnknown: boolean; includeCustomer: boolean;
};
export type Result = Facility & { distanceMeters: number; totalCost: number | null; evidence: Evidence; reasons: string[]; hoursState: 'open' | 'closed' | 'unknown' };
export const COVERAGE = { name: 'Connaught Place, New Delhi', west: 77.212, east: 77.224, south: 28.626, north: 28.638 };
export function haversine(a: Point, b: Point): number {
  const rad = Math.PI / 180;
  const dlat = (b.lat - a.lat) * rad, dlng = (b.lng - a.lng) * rad;
  const x = Math.sin(dlat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dlng / 2) ** 2;
  return 6371008.8 * 2 * Math.atan2(Math.sqrt(Math.min(1, x)), Math.sqrt(Math.max(0, 1 - x)));
}
export function inCoverage(p: Point): boolean {
  return p.lat >= COVERAGE.south && p.lat <= COVERAGE.north && p.lng >= COVERAGE.west && p.lng <= COVERAGE.east;
}
export function distanceLabel(meters: number): string {
  return meters < 1000 ? `${Math.round(meters / 10) * 10} m` : `${(meters / 1000).toFixed(1)} km`;
}
export function selectEvidence(items: Observation[], now = Date.now()): Evidence {
  const empty: Evidence = { state: 'UNKNOWN', evidenceClass: 'STATIC_LISTING', label: 'Mapped parking', source: null, observedAt: null, expiresAt: null, conflict: false };
  const current = items.filter(o => o.source.trim() && Number.isFinite(Date.parse(o.observedAt)) && Date.parse(o.observedAt) <= now && Date.parse(o.expiresAt) > now && Date.parse(o.expiresAt) > Date.parse(o.observedAt));
  current.sort((a,b)=>Date.parse(b.observedAt)-Date.parse(a.observedAt)||a.id.localeCompare(b.id));
  const seen=new Set<string>();
  const valid=current.filter(o=>{const key=`${o.evidenceClass}:${o.source}`;if(seen.has(key))return false;seen.add(key);return true;});
  if (!valid.length) return empty;
  const priority = (o: Observation) => o.evidenceClass === 'OPERATOR_REPORTED' ? 2 : 1;
  valid.sort((a, b) => priority(b) - priority(a) || Date.parse(b.observedAt) - Date.parse(a.observedAt) || a.id.localeCompare(b.id));
  const chosen = valid[0];
  const conflict = valid.some(o => o.state !== 'UNKNOWN' && chosen.state !== 'UNKNOWN' && o.state !== chosen.state);
  if (conflict) return { ...empty, label: 'Updates differ', conflict: true, source: chosen.source, observedAt: chosen.observedAt, expiresAt: chosen.expiresAt };
  return { state: chosen.state, evidenceClass: chosen.evidenceClass, label: chosen.evidenceClass === 'OPERATOR_REPORTED' ? 'Operator update' : 'Community report', source: chosen.source, observedAt: chosen.observedAt, expiresAt: chosen.expiresAt, conflict: false };
}
export function hoursAt(hours: Hours[] | null, at: string): 'open' | 'closed' | 'unknown' {
  if (!hours?.length || !Number.isFinite(Date.parse(at))) return 'unknown';
  const d = new Date(Date.parse(at) + 330 * 60000); // All pilot facilities use Asia/Kolkata, no DST.
  const day = d.getUTCDay(), min = d.getUTCHours() * 60 + d.getUTCMinutes();
  const today = hours.filter(h => h.day === day), yesterday = hours.filter(h => h.day === (day + 6) % 7);
  if (yesterday.some(h => !h.closed && h.overnight && min < h.closes)) return 'open';
  if (!today.length) return 'unknown';
  return today.some(h => !h.closed && (h.overnight ? min >= h.opens : min >= h.opens && min < h.closes)) ? 'open' : 'closed';
}
export function priceFor(rate: Rate | null, minutes: number): number | null {
  if (!rate || !rate.source || !rate.checkedAt || rate.currency !== 'INR' || !Number.isFinite(rate.amount) || rate.amount < 0) return null;
  if (rate.unit === 'PER_ENTRY') return rate.amount;
  if (rate.unit === 'PER_HOUR') return Math.ceil(minutes / 60) * rate.amount;
  if (rate.unit === 'PER_DAY') return Math.ceil(minutes / 1440) * rate.amount;
  return null;
}
export function searchFacilities(facilities: Facility[], observations: Observation[], input: SearchInput, now = Date.now()): Result[] {
  const result: Result[] = [];
  for (const f of facilities) {
    if (!f.active || f.access === 'PRIVATE' || f.access === 'PERMIT') continue;
    if (f.access === 'CUSTOMERS_ONLY' && !input.includeCustomer) continue;
    if (!input.includeUnknown && (f.access === 'UNKNOWN' || !f.vehicles.length || !f.hours?.length || !f.rate)) continue;
    if (f.vehicles.length && !f.vehicles.includes(input.vehicle)) continue;
    if (input.type !== 'all' && f.type !== input.type) continue;
    if (input.requirements.some(r => !f.features.includes(r))) continue;
    const hoursState = hoursAt(f.hours, input.arrivalAt);
    if (hoursState === 'closed') continue;
    const distanceMeters = haversine(input.destination, f.point);
    if (distanceMeters > input.radius) continue;
    const evidence = selectEvidence(observations.filter(o => o.facilityId === f.id), now);
    const totalCost = priceFor(f.rate, input.durationMinutes);
    const reasons = [`${distanceLabel(distanceMeters)} from your destination`, f.type === 'underground' ? 'Underground parking' : f.type === 'street_side' ? 'Street-side parking' : 'Surface parking'];
    if (f.sources.some(s => s.name === 'New Delhi Municipal Council')) reasons.push('Listed by NDMC');
    if (f.access === 'CUSTOMERS_ONLY') reasons.push('For customers of this venue');
    if (f.access === 'UNKNOWN') reasons.push('Check access before arrival');
    result.push({ ...f, distanceMeters: Math.round(distanceMeters), totalCost, evidence, reasons, hoursState });
  }
  return result.sort((a, b) => (input.sort === 'price' ? (a.totalCost ?? Infinity) - (b.totalCost ?? Infinity) || a.distanceMeters - b.distanceMeters : a.distanceMeters - b.distanceMeters) || a.id.localeCompare(b.id)).slice(0, 30);
}
export function navigationUrl(point: Point, mode: 'driving' | 'walking', origin?: Point): string {
  const p = new URLSearchParams({ api: '1', destination: `${point.lat},${point.lng}`, travelmode: mode });
  if (origin) p.set('origin', `${origin.lat},${origin.lng}`);
  return `https://www.google.com/maps/dir/?${p}`;
}
export function canManage(actor: { userId: string; role: string; facilityIds: string[] } | null, id: string): boolean {
  return !!actor && (actor.role === 'ADMIN' || actor.role === 'OPERATOR' && actor.facilityIds.includes(id));
}
