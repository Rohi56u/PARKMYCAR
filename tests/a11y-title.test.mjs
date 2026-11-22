import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

test('A11y Issue 3 [MEDIUM]: RootLayout contains non-empty <title> in <head>', () => {
  const layoutPath = join(process.cwd(), 'app', 'layout.tsx');
  const layout = readFileSync(layoutPath, 'utf-8');

  // Must contain <head><title>...</title></head>
  assert.ok(
    /<head>[\s\S]*<title>[^<]+<\/title>[\s\S]*<\/head>/.test(layout),
    'RootLayout must explicitly declare <head><title>...</title></head>'
  );

  // Must have root metadata with non-empty title
  assert.ok(
    layout.includes("title:'ParkMyCar — Park near your plans'") || layout.includes('title: "ParkMyCar — Park near your plans"'),
    'RootLayout must define non-empty metadata.title'
  );
});

test('A11y Issue 3 [MEDIUM]: Sub-routes have explicit document titles', () => {
  const researchPath = join(process.cwd(), 'app', 'research', 'page.tsx');
  const research = readFileSync(researchPath, 'utf-8');
  assert.ok(
    research.includes('metadata: Metadata = {') && research.includes('title:'),
    'Research page must export non-empty document title metadata'
  );

  const workspacePath = join(process.cwd(), 'app', 'workspace', 'page.tsx');
  const workspace = readFileSync(workspacePath, 'utf-8');
  assert.ok(
    workspace.includes('metadata: Metadata = {') && workspace.includes('title:'),
    'Workspace page must export non-empty document title metadata'
  );
});
