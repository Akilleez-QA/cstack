import { loadFoundation } from './registry.mjs';

const pick = (value, path) => path.split('.').reduce((node, name) => (node === null || node === undefined ? undefined : node[name]), value);

function decimal(number) {
  const [mantissa, exponent = '0'] = String(number).split('e');
  const [whole, fraction = ''] = mantissa.split('.');
  return { digits: BigInt(whole + fraction), scale: fraction.length - Number(exponent) };
}

export function withinTolerance(a, b, tolerance) {
  const [x, y, t] = [a, b, tolerance].map(decimal);
  const scale = Math.max(x.scale, y.scale, t.scale);
  const at = ({ digits, scale: own }) => digits * 10n ** BigInt(scale - own);
  const difference = at(x) - at(y);
  return (difference < 0n ? -difference : difference) <= at(t);
}

export async function judge(checks, outputs) {
  for (const check of checks) {
    const output = outputs.find(row => row.caseId === check.case);
    if (!output) return { passed: false, reason: `no output for case ${check.case}` };
    const foundation = await loadFoundation(check.foundation);
    if (!foundation) return { passed: false, reason: `judge has no Foundation ${check.foundation}` };
    const expected = pick(foundation.run(check.tool, JSON.stringify(check.arguments)), check.path);
    const agrees = typeof expected === 'number' ? typeof output.value === 'number' && withinTolerance(output.value, expected, check.tolerance)
      : typeof expected === 'string' && output.value === expected;
    if (!agrees) return { passed: false, reason: `case ${check.case} differs from the Foundation's own result` };
  }
  return { passed: true, reason: `${checks.length} held-out checks agree with the pinned Foundation` };
}
