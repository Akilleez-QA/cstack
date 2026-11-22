import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import type { IntentContract, IntentRef } from '@cstack/contracts';
import { HOST, LIFECYCLE, initial, refOf, transition, type IntentEvent, type IntentState } from '@cstack/intent';
import { artifactDigest } from '@cstack/acceptance';
export { sample } from '../../intent/test/helpers.ts';

export const OWNER = 'owner';

export const GOOD = `
export function clamp({ xs, lo, hi }) {
  for (let i = 0; i < xs.length; i++) xs[i] = xs[i] < lo ? lo : xs[i] > hi ? hi : xs[i];
  return xs;
}
if (process.argv.includes('--self-check')) {
  const out = clamp({ xs: [-5, 0, 9], lo: 0, hi: 3 });
  process.exit(out.join() === '0,0,3' ? 0 : 1);
}
`;

/** Writes a one-file artifact and returns its directory. */
export function artifact(source: string): string {
  const dir = mkdtempSync(join(tmpdir(), 'cstack-acceptance-'));
  writeFileSync(join(dir, 'clamp.mjs'), source);
  return dir;
}

export function apply(state: IntentState, ...events: IntentEvent[]): IntentState {
  for (const e of events) {
    const out = transition(state, e);
    if (!out.ok) throw new Error(`${e.type} refused: ${out.refusal}`);
    state = out.state;
  }
  return state;
}

/** A contract proposed, built and delivered from `dir`, with the confirm card unanswered. */
export function delivered(contract: IntentContract, dir: string) {
  const ref = refOf(contract);
  const sha = artifactDigest(dir);
  const state = apply(initial(OWNER),
    { type: 'intent_drafted', by: 'chief', contract },
    { type: 'intent_proposed', by: 'chief', ref },
    { type: 'derived', by: 'smith', ref, artifact_sha256: sha, what: 'kernel' },
    { type: 'delivery_recorded', by: LIFECYCLE, ref, artifact_sha256: sha, how_to_run: contract.delivery.how_to_run });
  return { ref, sha, state };
}

export const confirm = (ref: IntentRef): IntentEvent =>
  ({ type: 'intent_confirmed', by: HOST, ref, approval: { approval_id: 'ap-1', approver: OWNER, subject_sha256: ref.sha256 } });
