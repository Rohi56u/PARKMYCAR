import { existsSync,writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
const [major,minor]=process.versions.node.split('.').map(Number);
if(major<22||(major===22&&minor<13))throw new Error('Use Node 24 LTS or Node >=22.13.');
if(!existsSync('.dev.vars'))writeFileSync('.dev.vars',`# Local development only. Never expose this server publicly.\nPARKMYCAR_TRUSTED_SITES_GATEWAY="1"\nPARKMYCAR_ALLOW_BOOTSTRAP="1"\nRATE_LIMIT_SALT="${randomBytes(32).toString('hex')}"\n`,{mode:0o600});
const result=spawnSync(process.execPath,['--import','./scripts/sites-env.mjs','./node_modules/wrangler/bin/wrangler.js','d1','migrations','apply','DB','--local','--config','local-d1.json','--persist-to','.wrangler/state'],{stdio:'inherit'});
if(result.error)throw result.error;if(result.status!==0)process.exit(result.status??1);
console.log('Local database is ready. Run pnpm dev, then open http://localhost:5173.');
