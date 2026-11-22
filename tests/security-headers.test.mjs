import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

test('Security Issue 5 [MEDIUM]: next.config.ts configures baseline security headers including X-Frame-Options', () => {
  const configPath = join(process.cwd(), 'next.config.ts');
  const config = readFileSync(configPath, 'utf-8');

  assert.ok(
    config.includes("key: 'X-Frame-Options'") && config.includes("value: 'DENY'"),
    'next.config.ts must configure X-Frame-Options: DENY'
  );
  assert.ok(
    config.includes("key: 'X-Content-Type-Options'") && config.includes("value: 'nosniff'"),
    'next.config.ts must configure X-Content-Type-Options: nosniff'
  );
  assert.ok(
    config.includes("key: 'Referrer-Policy'"),
    'next.config.ts must configure Referrer-Policy'
  );
});

test('Security Issue 5 [MEDIUM]: netlify.toml reinforces X-Frame-Options header', () => {
  const tomlPath = join(process.cwd(), 'netlify.toml');
  const toml = readFileSync(tomlPath, 'utf-8');

  assert.ok(
    toml.includes('X-Frame-Options = "DENY"'),
    'netlify.toml must specify X-Frame-Options = "DENY"'
  );
});
