import { KernelRefusal } from './common.mjs';
import { loadFoundation } from './registry.mjs';

const pick = (value, path) => path.split('.').reduce((node, name) => (node === null || node === undefined ? undefined : node[name]), value);

export async function judge(checks, outputs) {
  for (const check of checks) {
    const output = outputs.find(row => row.caseId === check.case);
    if (!output) return { passed: false, reason: `no output for case ${check.case}` };
    const foundation = await loadFoundation(check.foundation);
    if (!foundation) return { passed: false, reason: `judge has no Foundation ${check.foundation}` };
    let receipt;
    try { receipt = foundation.run(check.tool, JSON.stringify(check.arguments)); }
    catch (error) {
      if (!(error instanceof KernelRefusal)) throw error;
      return { passed: false, reason: `case ${check.case}: the Foundation refused its held-out check (${error.code})` };
    }
    const expected = pick(receipt, check.path);
    const agrees = typeof expected === 'number' ? typeof output.value === 'number' && Math.abs(output.value - expected) <= check.tolerance
      : typeof expected === 'string' && output.value === expected;
    if (!agrees) return { passed: false, reason: `case ${check.case} differs from the Foundation's own result` };
  }
  return { passed: true, reason: `${checks.length} held-out checks agree with the pinned Foundation` };
}
