// GENERATED from schema/intent.schema.json by scripts/gen.ts. Do not edit; run `npm run gen`.

/**
 * This interface was referenced by `IntentContract`'s JSON-Schema
 * via the `definition` "Sha256".
 */
export type Sha256 = string;
/**
 * This interface was referenced by `IntentContract`'s JSON-Schema
 * via the `definition` "Prose".
 */
export type Prose = string;
/**
 * This interface was referenced by `IntentContract`'s JSON-Schema
 * via the `definition` "Identifier".
 */
export type Identifier = string;
/**
 * RFC 3339.
 *
 * This interface was referenced by `IntentContract`'s JSON-Schema
 * via the `definition` "Timestamp".
 */
export type Timestamp = string;
/**
 * Any JSON value without floats.
 *
 * This interface was referenced by `IntentContract`'s JSON-Schema
 * via the `definition` "Json".
 */
export type Json =
  | null
  | boolean
  | number
  | string
  | Json[]
  | {
      [k: string]: Json;
    };

/**
 * cstack.intent/1: the one record from the owner's words to delivered software. Integers, strings, booleans, arrays and objects only; no floats, so the v1 canonical digest applies unchanged.
 */
export interface IntentContract {
  schema: 'cstack.intent/1';
  /**
   * Stable across revisions and restarts; not session-scoped.
   */
  intent_id: string;
  revision: number;
  /**
   * sha256 of the prior revision; null on revision 1.
   */
  supersedes: Sha256 | null;
  /**
   * The owner's text, verbatim and never rewritten. It stays in the owner's ledger.
   */
  owner_words: {
    text: Prose;
    channel: Identifier;
    received_at: Timestamp;
  };
  /**
   * Chief's reading of the owner's words.
   */
  restatement: {
    objective: Prose;
    /**
     * @maxItems 32
     */
    assumptions: Prose[];
    /**
     * @maxItems 32
     */
    exclusions: Prose[];
    /**
     * @maxItems 3
     */
    questions_asked: {
      q: Prose;
      owner_answer: Prose;
    }[];
  };
  /**
   * Who restated, who writes the spec and who builds. Acceptance authors must be none of the last two.
   */
  roles: {
    chief: Identifier;
    spec_writer: Identifier;
    builder: Identifier;
  };
  /**
   * @minItems 1
   * @maxItems 32
   */
  acceptance: AcceptanceTest[];
  delivery: DeliveryTarget;
  limits: {
    budget_cents: number;
    model_runs: 'none' | 'stand-in' | 'real';
    deadline: Timestamp | null;
  };
}
/**
 * This interface was referenced by `IntentContract`'s JSON-Schema
 * via the `definition` "AcceptanceTest".
 */
export interface AcceptanceTest {
  id: Identifier;
  /**
   * Plain words the owner reads on the card.
   */
  says: string;
  /**
   * Bot id; never the spec writer or the builder.
   */
  author: string;
  check: ExampleCheck | PropertyCheck | CommandCheck | OwnerCheck;
}
/**
 * This interface was referenced by `IntentContract`'s JSON-Schema
 * via the `definition` "ExampleCheck".
 */
export interface ExampleCheck {
  kind: 'example';
  call: Identifier;
  inputs: Json;
  expect: Json;
  tolerance_ulps: number;
}
/**
 * This interface was referenced by `IntentContract`'s JSON-Schema
 * via the `definition` "PropertyCheck".
 */
export interface PropertyCheck {
  kind: 'property';
  call: Identifier;
  domain: Json;
  predicate: Prose;
  samples: number;
}
/**
 * This interface was referenced by `IntentContract`'s JSON-Schema
 * via the `definition` "CommandCheck".
 */
export interface CommandCheck {
  kind: 'command';
  /**
   * @minItems 1
   * @maxItems 256
   */
  argv: string[];
  expect_exit: number;
  expect_stdout_sha256?: Sha256;
}
/**
 * The owner judges this one. It is never automatic.
 *
 * This interface was referenced by `IntentContract`'s JSON-Schema
 * via the `definition` "OwnerCheck".
 */
export interface OwnerCheck {
  kind: 'owner_check';
  prompt: Prose;
}
/**
 * This interface was referenced by `IntentContract`'s JSON-Schema
 * via the `definition` "DeliveryTarget".
 */
export interface DeliveryTarget {
  kind: 'kernel' | 'package' | 'branch' | 'service';
  /**
   * @minItems 1
   * @maxItems 256
   */
  how_to_run: string[];
  where: Prose;
}
/**
 * Carried by everything downstream: specs, forge runs, candidates, PRs, receipts, verdicts.
 *
 * This interface was referenced by `IntentContract`'s JSON-Schema
 * via the `definition` "IntentRef".
 */
export interface IntentRef {
  intent_id: Identifier;
  revision: number;
  sha256: Sha256;
}
