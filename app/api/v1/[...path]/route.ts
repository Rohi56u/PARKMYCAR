import { env } from 'cloudflare:workers';
import { getChatGPTUser } from '../../../chatgpt-auth';
import { handleApi } from '../../../../lib/service';
import type { Database } from '../../../../lib/store';
export const dynamic='force-dynamic';
async function handler(request:Request) {
  const config=env as unknown as Record<string,unknown>;
  const trusted=config.PARKMYCAR_TRUSTED_SITES_GATEWAY==='1';
  const user=trusted?await getChatGPTUser():null;
  const rawKey=user?.userId??request.headers.get('cf-connecting-ip')??'local';
  const date=new Date().toISOString().slice(0,10);
  const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(`${config.RATE_LIMIT_SALT??'local'}:${date}:${rawKey}`));
  const rateKey=Array.from(new Uint8Array(hash)).map(n=>n.toString(16).padStart(2,'0')).join('');
  if(!env.DB)return Response.json({error:{code:'DATABASE',message:'The directory is temporarily unavailable. Please try again shortly.'}},{status:503});
  return handleApi(request,{db:env.DB as unknown as Database,identity:user?{userId:user.userId,displayName:user.displayName}:null,allowBootstrap:trusted&&config.PARKMYCAR_ALLOW_BOOTSTRAP==='1',rateKey,statusTtlMinutes:Number(config.PARKMYCAR_STATUS_TTL_MINUTES),geocoding:{baseUrl:typeof config.PARKMYCAR_PHOTON_BASE_URL==='string'?config.PARKMYCAR_PHOTON_BASE_URL:undefined}});
}
export {handler as GET,handler as POST,handler as PATCH,handler as DELETE};
