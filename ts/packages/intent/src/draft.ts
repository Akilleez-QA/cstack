// Checks a drafted contract before it can be proposed: schema, then the rules the schema can't say.
import { canonical, schemaProblems, type AcceptanceTest, type IntentContract } from '@cstack/contracts';

// A predicate that is true for every input can't fail (E11).
const ALWAYS_TRUE = /^\s*(?:\(?\s*[\w$,\s]*\)?\s*=>\s*)?\{?\s*(?:return\s+)?(?:true|!0|1|!!1)\s*;?\s*\}?\s*$/;
const ALWAYS_EXIT_0 = new Set(['true', ':']);

/** Why this acceptance test can't fail, or null when it can. */
export function cannotFail(test: AcceptanceTest): string | null {
  const c = test.check;
  switch (c.kind) {
    case 'example':
      return canonical(c.expect) === canonical(c.inputs) ? 'its expectation equals its input' : null;
    case 'property':
      return ALWAYS_TRUE.test(c.predicate) ? 'its predicate is true for every input' : null;
    case 'command':
      return ALWAYS_EXIT_0.has(c.argv[0] ?? "") && c.argv.length === 1 && c.expect_exit === 0 && !c.expect_stdout_sha256
        ? `\`${c.argv[0]}\` always exits 0` : null;
    case 'owner_check':
      return null;
  }
}

/** Every reason this draft is refused; [] means it may be proposed. */
export function draftProblems(value: unknown): string[] {
  const problems = schemaProblems(value);
  if (problems.length) return problems;
  const contract = value as IntentContract;
  if ((contract.revision === 1) !== (contract.supersedes === null))
    problems.push('supersedes must be null on revision 1 and a digest after it');
  const { spec_writer, builder } = contract.roles;
  const seen = new Set<string>();
  for (const test of contract.acceptance) {
    if (seen.has(test.id)) problems.push(`acceptance ${test.id}: duplicate id`);
    seen.add(test.id);
    if (test.author === spec_writer || test.author === builder)
      problems.push(`acceptance ${test.id}: written by ${test.author}, who ${test.author === builder ? 'builds' : 'writes the spec'}; acceptance tests are written independently`);
    const why = cannotFail(test);
    if (why) problems.push(`acceptance ${test.id}: can't fail, because ${why}`);
  }
  return problems;
}
