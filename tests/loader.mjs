import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const extensions = ['.ts', '.tsx', '.js', '.mjs', '.json'];

export async function resolve(specifier, context, nextResolve) {
  if (specifier.startsWith('./') || specifier.startsWith('../')) {
    if (context.parentURL && context.parentURL.startsWith('file:')) {
      const parentDir = path.dirname(fileURLToPath(context.parentURL));
      const resolvedBasePath = path.resolve(parentDir, specifier);

      for (const ext of extensions) {
        const checkPath = resolvedBasePath + ext;
        if (fs.existsSync(checkPath) && fs.statSync(checkPath).isFile()) {
          return nextResolve(pathToFileURL(checkPath).href, context);
        }
      }

      if (fs.existsSync(resolvedBasePath) && fs.statSync(resolvedBasePath).isDirectory()) {
        for (const ext of extensions) {
          const indexPath = path.join(resolvedBasePath, `index${ext}`);
          if (fs.existsSync(indexPath) && fs.statSync(indexPath).isFile()) {
            return nextResolve(pathToFileURL(indexPath).href, context);
          }
        }
      }
    }
  }

  return nextResolve(specifier, context);
}
