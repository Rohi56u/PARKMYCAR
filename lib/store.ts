import { initialFacilities, CATALOGUE_VERSION } from './catalogue.ts';
import type { Facility, Observation, Point } from './domain.ts';
import { ApiError } from './contracts.ts';
export type Member = { userId:string; role:'ADMIN'|'OPERATOR'|'REVIEWER'; displayName:string; facilityIds:string[] };
export type SqlResult<T> = { results:T[]; meta?:{changes?:number} };
export interface Statement { bind(...values:unknown[]):Statement; first<T=Record<string,unknown>>(column?:string):Promise<T|null>; all<T=Record<string,unknown>>():Promise<SqlResult<T>>; run():Promise<SqlResult<never>> }
export interface Database { prepare(sql:string):Statement; batch<T=unknown>(statements:Statement[]):Promise<SqlResult<T>[]> }
export class Store {
  db:Database;
  constructor(db:Database) { this.db=db; }
  async seed() {
    const existing=await this.db.prepare('SELECT value FROM settings WHERE key = ?').bind('catalogue_version').first();
    if (existing) return;
    const statements=initialFacilities.map(f=>this.db.prepare('INSERT OR IGNORE INTO facilities(id,name,lat,lng,active,version,payload) VALUES(?,?,?,?,?,?,?)').bind(f.id,f.name,f.point.lat,f.point.lng,1,1,JSON.stringify(f)));
    statements.push(this.db.prepare('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)').bind('catalogue_version',CATALOGUE_VERSION));
    await this.db.batch(statements);
  }
  async facilities(point?:Point,radius=2500):Promise<Facility[]> {
    let statement:Statement;
    if (point) {
      const latDelta=radius/110000, lngDelta=radius/(110000*Math.cos(point.lat*Math.PI/180));
      statement=this.db.prepare('SELECT payload,version,active FROM facilities WHERE active=1 AND lat BETWEEN ? AND ? AND lng BETWEEN ? AND ? LIMIT 200').bind(point.lat-latDelta,point.lat+latDelta,point.lng-lngDelta,point.lng+lngDelta);
    } else statement=this.db.prepare('SELECT payload,version,active FROM facilities ORDER BY name LIMIT 200');
    const r=await statement.all<{payload:string;version:number;active:number}>();
    return r.results.map(r=>({...JSON.parse(r.payload),version:r.version,active:!!r.active}));
  }
  async facility(id:string):Promise<Facility> {
    const row=await this.db.prepare('SELECT payload,version,active FROM facilities WHERE id=?').bind(id).first<{payload:string;version:number;active:number}>();
    if(!row)throw new ApiError(404,'NOT_FOUND','Parking location not found.');
    return {...JSON.parse(row.payload),version:row.version,active:!!row.active};
  }
  async observations(now=new Date().toISOString()):Promise<Observation[]> {
    const rows=await this.db.prepare('SELECT id,facility_id as facilityId,state,evidence_class as evidenceClass,source,observed_at as observedAt,expires_at as expiresAt FROM observations WHERE expires_at>? ORDER BY observed_at DESC LIMIT 1000').bind(now).all<Observation>(); return rows.results;
  }
  async member(id:string):Promise<Member|null> {
    const m=await this.db.prepare('SELECT user_id,role,display_name,facility_ids FROM members WHERE user_id=?').bind(id).first<{user_id:string;role:Member['role'];display_name:string;facility_ids:string}>();
    return m?{userId:m.user_id,role:m.role,displayName:m.display_name,facilityIds:JSON.parse(m.facility_ids)}:null;
  }
  async owner():Promise<string|null> { const row=await this.db.prepare('SELECT value FROM settings WHERE key=?').bind('owner').first<{value:string}>();return row?.value??null; }
  auditStatement(actorId:string,action:string,entityId:string,fields:string[]) {
    return this.db.prepare('INSERT INTO audit_events(id,actor_id,action,entity_id,fields,created_at) VALUES(?,?,?,?,?,?)').bind(crypto.randomUUID(),actorId,action,entityId,JSON.stringify(fields),new Date().toISOString());
  }
  async limit(key:string,max:number,seconds:number,now=Date.now()) {
    const bucket=Math.floor(now/(seconds*1000)),full=`${key}:${bucket}`;
    const row=await this.db.prepare('INSERT INTO request_limits(key,count,expires_at) VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1 RETURNING count').bind(full,(bucket+1)*seconds*1000).first<{count:number}>();
    if((row?.count??max+1)>max)throw new ApiError(429,'RATE_LIMIT','Please wait a moment before trying again.');
  }
  async prune(now=Date.now()) {
    const day=new Date(now).toISOString().slice(0,10);
    const r=await this.db.prepare('SELECT value FROM settings WHERE key=?').bind('last_prune').first<{value:string}>(); if(r?.value===day)return;
    await this.db.batch([
      this.db.prepare('DELETE FROM request_limits WHERE expires_at<?').bind(now),
      this.db.prepare('DELETE FROM geocode_cache WHERE expires_at<?').bind(now),
      this.db.prepare('DELETE FROM reports WHERE created_at<?').bind(new Date(now-30*86400000).toISOString()),
      this.db.prepare('DELETE FROM observations WHERE expires_at<?').bind(new Date(now-30*86400000).toISOString()),
      this.db.prepare('DELETE FROM audit_events WHERE created_at<?').bind(new Date(now-180*86400000).toISOString()),
      this.db.prepare('DELETE FROM listing_changes WHERE status<>? AND created_at<?').bind('PENDING',new Date(now-90*86400000).toISOString()),
      this.db.prepare('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value').bind('last_prune',day),
    ]);
  }
}
