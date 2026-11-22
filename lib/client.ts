export async function api<T>(path:string,body?:unknown,method=body?'POST':'GET',signal?:AbortSignal,headers?:Record<string,string>):Promise<T> {
  const mergedHeaders: Record<string, string> = {
    ...(body ? {'Content-Type': 'application/json'} : {}),
    ...(headers ?? {}),
  };
  const response=await fetch(`/api/v1/${path}`,{method,signal,headers:Object.keys(mergedHeaders).length?mergedHeaders:undefined,body:body?JSON.stringify(body):undefined});
  let data:T & {error?:{message?:string}};try{data=await response.json() as T & {error?:{message?:string}};}catch{throw new Error('The server could not complete this request. Please try again.');}if(!response.ok)throw new Error(data.error?.message??'Please try again.');return data;
}
export function readSaved():string[] {
  try {const value=JSON.parse(localStorage.getItem('parkmycar.saved')??'[]');return Array.isArray(value)?[...new Set(value.filter((v:unknown)=>typeof v==='string'&&/^[a-z0-9-]{1,60}$/.test(v)))].slice(0,3) as string[]:[];}catch{return [];}
}
export function storeSaved(ids:string[]):boolean {try{localStorage.setItem('parkmycar.saved',JSON.stringify(ids.slice(0,3)));return true;}catch{return false;}}
