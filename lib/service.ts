import { z } from 'zod';
import { findPlaces, type GeocodingOptions } from './geocoding.ts';
import { Store, type Database, type Member } from './store.ts';
import { destinations, CATALOGUE_VERSION } from './catalogue.ts';
import { COVERAGE, canManage, searchFacilities, selectEvidence, haversine, inCoverage, type Facility } from './domain.ts';
import { ApiError, searchSchema, reportSchema, observationSchema, listingSchema, memberSchema, importSchema, placeSearchSchema, readBody, requireSameOrigin, requireRecent } from './contracts.ts';
export type Identity = { userId:string; displayName:string } | null;
export type ServiceOptions = { db:Database; identity:Identity; allowBootstrap:boolean; rateKey:string; now?:number; statusTtlMinutes?:number; geocoding?:GeocodingOptions };
const headers = { 'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'strict-origin-when-cross-origin' };
function json(data:unknown,status=200) { return new Response(JSON.stringify(data),{status,headers}); }
async function requireMember(store:Store,identity:Identity,roles:string[]):Promise<Member> {
  if(!identity)throw new ApiError(401,'SIGN_IN','Sign in to open the workspace.');
  const member=await store.member(identity.userId);
  if(!member||!roles.includes(member.role))throw new ApiError(403,'FORBIDDEN','Your account does not have permission for this action.'); return member;
}
async function applyListing(store:Store,actor:Member,f:Facility,payload:z.infer<typeof listingSchema>,changeId?:string) {
  if(f.version!==payload.version)throw new ApiError(409,'STALE_VERSION','This listing changed. Refresh before saving.');
  const {sourceName,sourceUrl,version,...patch}=payload;const checkedAt=new Date().toISOString();
  const next:Facility={...f,...patch,version:version+1,verification:'REVIEWED',rate:patch.rate?{...patch.rate,source:sourceUrl,checkedAt}:null,sources:[...f.sources.slice(-7),{name:sourceName,url:sourceUrl,fields:['name','access','type','entry notes','vehicles','features','hours','rate'],checkedAt,license:'Submitted factual reference'}]};
  // Compare-and-swap plus audit inserted from the same matched row: one atomic D1 batch.
  const auditId=crypto.randomUUID(),auditFields=JSON.stringify(Object.keys(patch));
  const statements=[
    store.db.prepare('INSERT INTO audit_events(id,actor_id,action,entity_id,fields,created_at) SELECT ?,?,?,?,?,? FROM facilities WHERE id=? AND version=?').bind(auditId,actor.userId,'LISTING_UPDATED',f.id,auditFields,checkedAt,f.id,version),
    store.db.prepare('UPDATE facilities SET name=?,active=?,version=version+1,payload=? WHERE id=? AND version=?').bind(next.name,next.active?1:0,JSON.stringify(next),f.id,version),
  ];
  if(changeId) statements.push(store.db.prepare('UPDATE listing_changes SET status=? WHERE id=? AND EXISTS(SELECT 1 FROM audit_events WHERE id=?)').bind('APPROVED',changeId,auditId));
  const result=await store.db.batch(statements);if(!result[1].meta?.changes)throw new ApiError(409,'STALE_VERSION','This listing changed. Refresh before saving.');
  return next;
}
export async function handleApi(request:Request,options:ServiceOptions):Promise<Response> {
  const requestId=crypto.randomUUID(); const now=options.now??Date.now();
  const requestedTtl=options.statusTtlMinutes;
  const statusTtlMinutes=typeof requestedTtl==='number'&&Number.isInteger(requestedTtl)&&requestedTtl>=5&&requestedTtl<=60?requestedTtl:15;
  try {
    const url=new URL(request.url),path=url.pathname.replace(/^\/api\/v1\/?/,'').split('/').filter(Boolean),method=request.method;
    const store=new Store(options.db); await store.seed(); await store.prune(now);
    if(method==='GET'&&path[0]==='health')return json({status:'ok',catalogueVersion:CATALOGUE_VERSION});
    if(method==='GET'&&path[0]==='bootstrap')return json({destinations,catalogue:(await store.facilities()).filter(f=>f.active&&f.access!=='PRIVATE'&&f.access!=='PERMIT'),coverage:COVERAGE,catalogueVersion:CATALOGUE_VERSION,serverTime:new Date(now).toISOString()});
    if(method==='POST'&&path[0]==='places'&&path[1]==='search'&&path.length===2) {
      requireSameOrigin(request);
      const p=await readBody(request,placeSearchSchema);
      await store.limit(`places:${options.rateKey}`,20,60,now);
      return json(await findPlaces(store,p.query,now,options.geocoding));
    }
    if(method==='POST'&&path[0]==='search') {
      await store.limit(`search:${options.rateKey}`,90,60,now);
      const input=await readBody(request,searchSchema);
      const [facilities,observations]=await Promise.all([store.facilities(input.destination,input.radius),store.observations(new Date(now).toISOString())]);
      return json({results:searchFacilities(facilities,observations,input,now),coverage:COVERAGE,serverTime:new Date(now).toISOString(),distanceBasis:'straight_line',catalogueVersion:CATALOGUE_VERSION});
    }
    if(method==='GET'&&path[0]==='facilities'&&path[1]) {
      const f=await store.facility(path[1]);if(!f.active||f.access==='PRIVATE'||f.access==='PERMIT')throw new ApiError(404,'NOT_FOUND','This parking location is no longer listed.');
      const observations=await store.observations(new Date(now).toISOString());return json({facility:f,evidence:selectEvidence(observations.filter(o=>o.facilityId===f.id),now)});
    }
    if(method==='POST'&&path[0]==='reports') {
      requireSameOrigin(request);await store.limit(`report:${options.rateKey}`,3,600,now);
      const p=await readBody(request,reportSchema);requireRecent(p.observedAt,now);
      const f=await store.facility(p.facilityId);if(!f.active||f.access==='PRIVATE'||f.access==='PERMIT')throw new ApiError(404,'NOT_FOUND','This parking location is no longer listed.');
      const dedup=`${options.rateKey}:${p.facilityId}:${Math.floor(now/900000)}`;
      const id=crypto.randomUUID();
      const r=await store.db.prepare('INSERT OR IGNORE INTO reports(id,facility_id,category,observed_at,created_at,status,dedup_key) VALUES(?,?,?,?,?,?,?)').bind(id,p.facilityId,p.category,new Date(p.observedAt).toISOString(),new Date(now).toISOString(),'PENDING',dedup).run();
      if(!r.meta?.changes)throw new ApiError(409,'DUPLICATE','You have already reported this location recently.');
      return json({id,status:'PENDING',message:'Report received. It will be checked before being published.'},201);
    }
    if(path[0]==='workspace') {
      if(method==='GET'&&path.length===1) {
        if(!options.identity)return json({signedIn:false,member:null,canClaim:false});
        const member=await store.member(options.identity.userId),owner=await store.owner();
        if(!member)return json({signedIn:true,userId:options.identity.userId,displayName:options.identity.displayName,member:null,canClaim:options.allowBootstrap&&!owner});
        const all=await store.facilities();const facilities=member.role==='OPERATOR'?all.filter(f=>member.facilityIds.includes(f.id)):all;
        const [reports,changes,events,team]=member.role==='OPERATOR'?[{results:[]},{results:[]},{results:[]},{results:[]}]:await Promise.all([
          store.db.prepare('SELECT id,facility_id,category,observed_at,created_at,status FROM reports ORDER BY created_at DESC LIMIT 100').all(),
          store.db.prepare('SELECT id,facility_id,actor_id,payload,status,created_at FROM listing_changes ORDER BY created_at DESC LIMIT 100').all(),
          store.db.prepare('SELECT action,entity_id,fields,created_at FROM audit_events ORDER BY created_at DESC LIMIT 100').all(),
          member.role==='ADMIN'?store.db.prepare('SELECT user_id,role,display_name,facility_ids FROM members ORDER BY role,display_name').all():Promise.resolve({results:[]}),
        ]);
        return json({signedIn:true,userId:member.userId,member,facilities,reports:reports.results,changes:changes.results,events:events.results,team:team.results,canClaim:false,statusTtlMinutes});
      }
      requireSameOrigin(request);
      if(method==='POST'&&path[1]==='claim') {
        if(!options.identity||!options.allowBootstrap)throw new ApiError(403,'SETUP_DISABLED','Workspace setup is restricted to the private Site owner.');
        const existing=await store.owner();if(existing&&existing!==options.identity.userId)throw new ApiError(409,'ALREADY_OWNED','This workspace already has an owner.');
        await store.db.batch([
          store.db.prepare('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)').bind('owner',options.identity.userId),
          store.db.prepare('INSERT OR IGNORE INTO members(user_id,role,display_name,facility_ids) SELECT ?,?,?,? WHERE EXISTS(SELECT 1 FROM settings WHERE key=? AND value=?)').bind(options.identity.userId,'ADMIN',options.identity.displayName,'[]','owner',options.identity.userId),
        ]);
        const member=await store.member(options.identity.userId);if(!member)throw new ApiError(409,'ALREADY_OWNED','This workspace already has an owner.');return json({member},201);
      }
      const actor=await requireMember(store,options.identity,['ADMIN','OPERATOR','REVIEWER']);
      await store.limit(`workspace:${actor.userId}`,30,60,now);
      if(method==='POST'&&path[1]==='import') {
        if(actor.role!=='ADMIN')throw new ApiError(403,'FORBIDDEN','Only the owner can add sourced locations.');
        const p=await readBody(request,importSchema);
        if(!inCoverage(p.point))throw new ApiError(400,'COVERAGE','Add locations within the current Connaught Place coverage area.');
        const existing=await store.facilities();
        if(existing.some(f=>haversine(f.point,p.point)<15))throw new ApiError(409,'DUPLICATE_LOCATION','A location already exists within 15 metres. Review the existing listing first.');
        if(existing.length>=200)throw new ApiError(409,'CAPACITY','The pilot catalogue limit has been reached. Review the database scale plan before expanding.');
        const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(`${p.point.lat.toFixed(6)},${p.point.lng.toFixed(6)}:${p.sourceUrl}`));
        const id=`parking-${Array.from(new Uint8Array(hash)).slice(0,12).map(n=>n.toString(16).padStart(2,'0')).join('')}`;
        const f:Facility={id,name:p.name,area:COVERAGE.name,nameKind:'official',point:p.point,type:p.type,access:p.access,locationKind:'area_centroid',vehicles:[],features:[],hours:null,rate:null,entryNotes:p.entryNotes,active:true,verification:'REVIEWED',version:1,operatorId:null,sources:[{name:p.sourceName,url:p.sourceUrl,fields:['name','location','type','access'],checkedAt:new Date(now).toISOString(),license:p.license}]};
        await store.db.batch([store.db.prepare('INSERT INTO facilities(id,name,lat,lng,active,version,payload) VALUES(?,?,?,?,?,?,?)').bind(id,f.name,f.point.lat,f.point.lng,1,1,JSON.stringify(f)),store.auditStatement(actor.userId,'LOCATION_IMPORTED',id,['name','point','type','access','sources'])]);return json({facility:f},201);
      }
      if(method==='POST'&&path[1]==='members') {
        if(actor.role!=='ADMIN')throw new ApiError(403,'FORBIDDEN','Only the owner can manage the team.');
        const p=await readBody(request,memberSchema);if(p.userId===await store.owner())throw new ApiError(400,'OWNER','The workspace owner role cannot be changed.');
        for(const id of p.facilityIds)await store.facility(id);
        await store.db.batch([store.db.prepare('INSERT INTO members(user_id,role,display_name,facility_ids) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET role=excluded.role,display_name=excluded.display_name,facility_ids=excluded.facility_ids').bind(p.userId,p.role,p.displayName,JSON.stringify([...new Set(p.facilityIds)])),store.auditStatement(actor.userId,'MEMBER_UPDATED',p.userId,['role','facilityIds'])]);return json({ok:true});
      }
      if(method==='POST'&&path[1]==='members'&&path[2])throw new ApiError(404,'NOT_FOUND','Action not found.');
      if(method==='DELETE'&&path[1]==='members'&&path[2]) {
        if(actor.role!=='ADMIN'||decodeURIComponent(path[2])===await store.owner())throw new ApiError(403,'FORBIDDEN','This member cannot be removed.');
        await store.db.batch([store.db.prepare('DELETE FROM members WHERE user_id=?').bind(decodeURIComponent(path[2])),store.auditStatement(actor.userId,'MEMBER_REMOVED',decodeURIComponent(path[2]),[])]);return json({ok:true});
      }
      if(path[1]==='facilities'&&path[2]) {
        const f=await store.facility(path[2]);if(!canManage(actor,f.id))throw new ApiError(403,'FORBIDDEN','You can only update your assigned parking locations.');
        if(method==='PATCH'&&path.length===3) {
          const p=await readBody(request,listingSchema);
          if(f.version!==p.version)throw new ApiError(409,'STALE_VERSION','This listing changed. Refresh before saving.');
          if(actor.role==='ADMIN')return json({facility:await applyListing(store,actor,f,p)});
          const id=crypto.randomUUID();await store.db.batch([store.db.prepare('INSERT INTO listing_changes(id,facility_id,actor_id,payload,status,created_at) VALUES(?,?,?,?,?,?)').bind(id,f.id,actor.userId,JSON.stringify(p),'PENDING',new Date(now).toISOString()),store.auditStatement(actor.userId,'CHANGE_REQUESTED',f.id,Object.keys(p))]);return json({status:'PENDING',id},202);
        }
        if(method==='POST'&&path[3]==='status') {
          if(actor.role!=='OPERATOR')throw new ApiError(403,'OPERATOR_REQUIRED','Status observations must come from an assigned operator.');
          if(!f.active)throw new ApiError(409,'INACTIVE','This listing is inactive.');
          const p=await readBody(request,observationSchema);requireRecent(p.observedAt,now,statusTtlMinutes);
          const observedAt=new Date(p.observedAt).toISOString(),expiresAt=new Date(Date.parse(observedAt)+statusTtlMinutes*60000).toISOString();
          await store.db.batch([store.db.prepare('INSERT INTO observations(id,facility_id,state,evidence_class,source,observed_at,expires_at) VALUES(?,?,?,?,?,?,?)').bind(crypto.randomUUID(),f.id,p.state,'OPERATOR_REPORTED',actor.displayName,observedAt,expiresAt),store.auditStatement(actor.userId,'STATUS_REPORTED',f.id,['state','observedAt'])]);return json({ok:true,expiresAt},201);
        }
      }
      if(method==='POST'&&path[1]==='reports'&&path[2]&&path[3]==='moderate') {
        if(actor.role==='OPERATOR')throw new ApiError(403,'FORBIDDEN','Only reviewers can review reports.');
        const p=await readBody(request,z.object({decision:z.enum(['APPROVED','REJECTED','RESOLVED'])}).strict());
        const r=await store.db.prepare('SELECT * FROM reports WHERE id=?').bind(path[2]).first<{id:string;facility_id:string;category:string;observed_at:string;status:string}>();
        if(!r)throw new ApiError(404,'NOT_FOUND','Report not found.');if(r.status!=='PENDING')throw new ApiError(409,'ALREADY_REVIEWED','This report has already been reviewed.');
        if(p.decision==='APPROVED'&&Date.parse(r.observed_at)+statusTtlMinutes*60000<=now)throw new ApiError(409,'EXPIRED','This report is too old to publish as a current status. Resolve it instead.');
        const auditId=crypto.randomUUID();
        const stmts=[
          store.db.prepare('INSERT INTO audit_events(id,actor_id,action,entity_id,fields,created_at) SELECT ?,?,?,?,?,? FROM reports WHERE id=? AND status=?').bind(auditId,actor.userId,`REPORT_${p.decision}`,r.id,'[]',new Date(now).toISOString(),r.id,'PENDING'),
          store.db.prepare('UPDATE reports SET status=? WHERE id=? AND EXISTS(SELECT 1 FROM audit_events WHERE id=?)').bind(p.decision,r.id,auditId),
        ];
        if(p.decision==='APPROVED'&&['FULL','FOUND_SPACE'].includes(r.category))stmts.push(store.db.prepare('INSERT OR IGNORE INTO observations(id,facility_id,state,evidence_class,source,observed_at,expires_at) SELECT ?,?,?,?,?,?,? WHERE EXISTS(SELECT 1 FROM audit_events WHERE id=?)').bind(`report-${r.id}`,r.facility_id,r.category==='FULL'?'FULL':'AVAILABLE','COMMUNITY_REPORTED','Driver report',r.observed_at,new Date(Date.parse(r.observed_at)+statusTtlMinutes*60000).toISOString(),auditId));
        const applied=await store.db.batch(stmts);if(!applied[1].meta?.changes)throw new ApiError(409,'ALREADY_REVIEWED','Another reviewer has already reviewed this report.');return json({ok:true});
      }
      if(method==='POST'&&path[1]==='changes'&&path[2]&&path[3]==='moderate') {
        if(actor.role!=='ADMIN')throw new ApiError(403,'FORBIDDEN','Only the owner can publish listing changes.');
        const p=await readBody(request,z.object({decision:z.enum(['APPROVED','REJECTED'])}).strict());
        const r=await store.db.prepare('SELECT * FROM listing_changes WHERE id=?').bind(path[2]).first<{id:string;facility_id:string;payload:string;status:string}>();if(!r)throw new ApiError(404,'NOT_FOUND','Change not found.');if(r.status!=='PENDING')throw new ApiError(409,'ALREADY_REVIEWED','This change was already reviewed.');
        if(p.decision==='APPROVED')await applyListing(store,actor,await store.facility(r.facility_id),listingSchema.parse(JSON.parse(r.payload)),r.id);
        else await store.db.batch([store.db.prepare('UPDATE listing_changes SET status=? WHERE id=?').bind('REJECTED',r.id),store.auditStatement(actor.userId,'CHANGE_REJECTED',r.facility_id,[])]);return json({ok:true});
      }
    }
    throw new ApiError(404,'NOT_FOUND','This endpoint does not exist.');
  } catch(error) {
    if(error instanceof ApiError)return json({error:{code:error.code,message:error.message,requestId}},error.status);
    // Do not log request URLs, coordinates, addresses, SQL values, or credentials.
    console.error(JSON.stringify({event:'api_error',requestId,category:'internal'}));
    return json({error:{code:'INTERNAL',message:'Something went wrong. Please try again shortly.',requestId}},500);
  }
}
