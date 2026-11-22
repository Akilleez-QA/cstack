// The digest of a delivered artifact directory: the v1 digest of {relative path: sha256 of bytes}.
// The runner recomputes it before every run, so it tests exactly what was delivered.
import { createHash } from 'node:crypto';
import { lstatSync, readdirSync, readFileSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { digest } from '@cstack/contracts';

export function artifactFiles(dir: string): Record<string, string> {
  const files: Record<string, string> = {};
  const walk = (at: string) => {
    for (const name of readdirSync(at).sort()) {
      const path = join(at, name);
      const st = lstatSync(path);
      if (st.isSymbolicLink()) throw new Error(`artifact contains a symlink: ${relative(dir, path)}`);
      if (st.isDirectory()) walk(path);
      else if (st.isFile()) files[relative(dir, path).split(sep).join('/')] = createHash('sha256').update(readFileSync(path)).digest('hex');
    }
  };
  walk(dir);
  return files;
}

export function artifactDigest(dir: string): string {
  return digest(artifactFiles(dir));
}
