import { readFileSync } from 'node:fs';
import type { IntentContract } from '@cstack/contracts';

export const vectors = JSON.parse(readFileSync(new URL('../vectors/digest.json', import.meta.url), 'utf8')) as {
  vectors: { name: string; value: unknown; canonical: string; sha256: string }[];
  ts_refuses: { name: string; canonical: string }[];
};

/** A fresh copy of the sample contract from the Python vectors. */
export function sample(): IntentContract {
  return structuredClone(vectors.vectors.find((v) => v.name === 'contract')!.value) as IntentContract;
}
