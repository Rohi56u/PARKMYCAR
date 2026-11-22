import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

function relLum(hex) {
  const clean = hex.replace('#', '');
  const r = parseInt(clean.substring(0, 2), 16) / 255;
  const g = parseInt(clean.substring(2, 4), 16) / 255;
  const b = parseInt(clean.substring(4, 6), 16) / 255;
  const [rc, gc, bc] = [r, g, b].map(c =>
    c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
  );
  return 0.2126 * rc + 0.7152 * gc + 0.0722 * bc;
}

function contrast(c1, c2) {
  const l1 = relLum(c1);
  const l2 = relLum(c2);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

test('A11y Issue 2 [MEDIUM]: Contrast ratios meet WCAG 2 AA >= 4.5:1 on light backgrounds', () => {
  const cssPath = join(process.cwd(), 'app', 'globals.css');
  const css = readFileSync(cssPath, 'utf-8');

  // Verify key typography tokens have contrast >= 4.5:1 against light backgrounds (#ffffff / #f6f7f2)
  const mutedMatch = css.match(/--muted:\s*(#[0-9a-fA-F]{6})/);
  assert.ok(mutedMatch, '--muted definition exists');
  const mutedColor = mutedMatch[1];
  const mutedContrast = contrast(mutedColor, '#f6f7f2');
  assert.ok(
    mutedContrast >= 4.5,
    `--muted (${mutedColor}) contrast vs paper must be >= 4.5:1 (got ${mutedContrast.toFixed(2)})`
  );

  const primaryText = contrast('#47554d', '#f6f7f2');
  assert.ok(primaryText >= 4.5, `Updated secondary/muted color contrast must be >= 4.5:1 (got ${primaryText.toFixed(2)})`);

  // Ensure old failing low-contrast muted tokens (#707b73, #748074, #68776e) are absent
  assert.ok(!css.includes('#707b73'), 'Old low-contrast #707b73 must be removed');
  assert.ok(!css.includes('color:#748074'), 'Old low-contrast #748074 must be removed');
  assert.ok(!css.includes('color:#68776e'), 'Old low-contrast #68776e must be removed');
});

test('A11y Issue 2 [MEDIUM]: AnprDashboard secondary text meets WCAG 2 AA on dark background', () => {
  const anprPath = join(process.cwd(), 'components', 'AnprDashboard.tsx');
  const anpr = readFileSync(anprPath, 'utf-8');

  // Secondary text on dark background (#0f172a) must use #cbd5e1 (contrast ~11:1)
  const slate300Contrast = contrast('#cbd5e1', '#0f172a');
  assert.ok(slate300Contrast >= 4.5, `#cbd5e1 contrast must be >= 4.5:1 (got ${slate300Contrast.toFixed(2)})`);

  // Ensure low-contrast text on dark background (#94a3b8 / #64748b) has been replaced for text colors
  assert.ok(!anpr.includes("color: '#94a3b8'"), "Failing #94a3b8 text color must be removed");
  assert.ok(!anpr.includes("color: '#64748b'"), "Failing #64748b text color must be removed");
});
