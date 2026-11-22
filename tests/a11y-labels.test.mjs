import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

test('A11y Issue 1 [HIGH]: Every input in AnprDashboard has an accessible label', () => {
  const filePath = join(process.cwd(), 'components', 'AnprDashboard.tsx');
  const content = readFileSync(filePath, 'utf-8');

  // Verify file upload input has an accessible label
  assert.ok(
    content.includes('id="anpr-file-input"'),
    'File upload input must have id="anpr-file-input"'
  );
  assert.ok(
    content.includes('aria-label="Upload vehicle or number plate image"'),
    'File upload input must have aria-label'
  );
  assert.ok(
    content.includes('htmlFor="anpr-file-input"'),
    'File upload input must have associated <label htmlFor="anpr-file-input">'
  );

  // Verify registration text input has an accessible label
  assert.ok(
    content.includes('id="anpr-plate-input"'),
    'Plate text input must have id="anpr-plate-input"'
  );
  assert.ok(
    content.includes('aria-label="Enter vehicle registration number"'),
    'Plate text input must have aria-label'
  );
  assert.ok(
    content.includes('htmlFor="anpr-plate-input"'),
    'Plate text input must have associated <label htmlFor="anpr-plate-input">'
  );
});
