import { DatabaseSync } from 'node:sqlite';
import { readFileSync,readdirSync } from 'node:fs';
import type { Database,Statement,SqlResult } from '../lib/store.ts';
export class TestDatabase implements Database {
 raw:DatabaseSync;
 constructor(){this.raw=new DatabaseSync(':memory:');this.raw.exec('PRAGMA foreign_keys=ON');for(const file of readdirSync(new URL('../drizzle/',import.meta.url)).filter(f=>f.endsWith('.sql')).sort())this.raw.exec(readFileSync(new URL(`../drizzle/${file}`,import.meta.url),'utf8'));}
 prepare(sql:string):Statement {
  const db=this.raw;let values:unknown[]=[];
  const statement:Statement={bind(...args){values=args;return statement;},async first<T>(column?:string){const r=db.prepare(sql).get(...values as (string|number|null)[]);return (column?r?.[column]:r??null) as T|null;},async all<T>(){return {results:db.prepare(sql).all(...values as (string|number|null)[]) as T[]};},async run(){const r=db.prepare(sql).run(...values as (string|number|null)[]);return {results:[],meta:{changes:Number(r.changes)}};}};return statement;
 }
 async batch<T>(statements:Statement[]):Promise<SqlResult<T>[]> {this.raw.exec('BEGIN');try{const out=[];for(const s of statements)out.push(await s.run());this.raw.exec('COMMIT');return out as SqlResult<T>[];}catch(e){this.raw.exec('ROLLBACK');throw e;}}
 close(){this.raw.close();}
}
