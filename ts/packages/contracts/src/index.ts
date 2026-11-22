import { Ajv2020, type ErrorObject } from 'ajv/dist/2020.js';
import schema from '../schema/intent.schema.json' with { type: 'json' };
import type { IntentContract, IntentRef } from './intent.generated.ts';

export type * from './intent.generated.ts';
export { canonical, digest, parseStrict, ContractError, MAX_DOCUMENT_BYTES } from './canonical.ts';
export { schema as intentSchema };

const ajv = new Ajv2020({ allErrors: true, strict: true });
ajv.addSchema(schema);
const contract = ajv.getSchema<IntentContract>(schema.$id)!;
const ref = ajv.compile<IntentRef>({ $ref: `${schema.$id}#/$defs/IntentRef` });

const explain = (errors: ErrorObject[] | null | undefined) =>
  (errors ?? []).map((e) => `${e.instancePath || '/'} ${e.message}`);

/** Schema problems for an intent contract; [] means it is well formed. */
export function schemaProblems(value: unknown): string[] {
  return contract(value) ? [] : explain(contract.errors);
}

export function isIntentRef(value: unknown): value is IntentRef {
  return ref(value);
}
