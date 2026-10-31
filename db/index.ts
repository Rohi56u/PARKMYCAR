import * as schema from "./schema";

export async function getDb() {
  try {
    const cf = await import(/* webpackIgnore: true */ "cloudflare:workers" as string);
    const env = (cf as { env?: { DB?: unknown } })?.env;
    if (env?.DB) {
      const { drizzle } = await import("drizzle-orm/d1");
      return drizzle(env.DB as any, { schema });
    }
  } catch {
    // Cloudflare D1 unavailable in Node / standard Next.js
  }
  return null;
}
