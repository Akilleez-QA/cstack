# Deployment checks pass; the feature fails

Synthetic example. The statements below are supplied scenario facts, not observations made by this repository.

## Prompt

```text
Use $poodo to assess our release. The source and deployment hashes match and
schema checks pass, but the user cannot complete the new export flow.
Inspect and propose the next test. Do not deploy changes.
```

## Decision point

The acceptance criterion is completion of an export through the user-facing flow. A schema check and a hash comparison concern different properties. The outcome claim must be withheld or retracted even while those narrow checks remain recorded as passing.

Two credible rivals are an implementation defect and a request reaching a different runtime than the checked artifact. Compare the failing request's destination and runtime identity with the inspected deployment, then reproduce the flow under the same inputs.

## Prospective test fragment

- Prediction: the recorded candidate completes the specified export in the named test environment.
- Oracle: the user can retrieve the complete expected export; freeze the expected dataset and criterion before testing.
- Artifact/environment: record commit, deployment identity, configuration, request route, and fixture identity.
- Authority: read-only inspection and an authorized test export; no deployment.
- Failure: record failure against this criterion, leaving cause unresolved until discriminated.
- Stop: pause if the test requires unapproved writes or production access.

## Honest handoff

`delivery_state: deployed` is a scenario report. `outcome_state: reported` applies to the user-reported failure until directly observed. Highest justified claim: the supplied checks do not establish the intended effect. The next authorized runtime observation belongs to the agent only if its tools and permissions can perform it.
