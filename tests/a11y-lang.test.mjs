import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

test('A11y Issue 4 [MEDIUM]: RootLayout and GlobalError have lang="en" on <html> element', () => {
  const layoutPath = join(process.cwd(), 'app', 'layout.tsx');
  const layout = readFileSync(layoutPath, 'utf-8');
  assert.ok(
    /<html[^>]*\blang=["']en["'][^>]*>/.test(layout),
    'RootLayout must define lang="en" on <html ...>'
  );

  const errorPath = join(process.cwd(), 'app', 'global-error.tsx');
  const errorPage = readFileSync(errorPath, 'utf-8');
  assert.ok(
    /<html[^>]*\blang=["']en["'][^>]*>/.test(errorPage),
    'global-error.tsx must define lang="en" on <html ...>'
  );
});

test('A11y Issue 4 [MEDIUM]: not-found.tsx is defined to avoid unstyled language-less error pages', () => {
  const notFoundPath = join(process.cwd(), 'app', 'not-found.tsx');
  const notFound = readFileSync(notFoundPath, 'utf-8');
  assert.ok(
    notFound.includes('NotFound') && notFound.includes('404'),
    'app/not-found.tsx must be defined'
  );
});
