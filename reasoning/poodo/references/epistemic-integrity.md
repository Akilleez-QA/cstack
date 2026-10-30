# Epistemic integrity and light red teaming

Read this reference for Deep POODO work, incident diagnosis, disputed evidence, or validation of a consequential system. Its purpose is to improve the reliability of reasoning, not to maximize skepticism or procedural overhead.

## Verification, validation, and claim scope

- **Verification** asks whether an artifact conforms to its specified requirements.
- **Validation** asks whether the resulting system satisfies the intended need in its operational environment.
- Build completion, artifact parity, schema conformance, and static checks are verification evidence. They do not substitute for validation when the claim concerns runtime or real-world behavior.
- Match the claim to the observed surface. A component test supports a component claim; an end-to-end claim requires evidence across the consequential handoffs.

NASA's IV&V guidance distinguishes building the product correctly from building the right product and emphasizes technical independence, objective acceptance criteria, operational context, and nominal and off-nominal behavior:

- https://www.nasa.gov/ivv-overview/
- https://swehb.nasa.gov/spaces/SWEHBVD/pages/102695499/SWE-141%2B-%2BSoftware%2BIndependent%2BVerification%2Band%2BValidation

## Oracle quality and evidence coupling

A test oracle is the basis for deciding whether observed behavior is correct. Before trusting a pass, ask:

1. What observation did the test actually make?
2. What rule classified it as pass or fail?
3. Where did that rule come from?
4. Does the rule rest on the same assumption as the implementation?
5. Could the system and oracle share the same defect?
6. Does the oracle assess the user's intended outcome or only an internal proxy?

Independence is a continuum. Prefer, in descending order as feasible:

- externally established acceptance criteria or operational observation;
- an independently derived reference implementation or evaluator;
- an orthogonal measurement mechanism;
- differential comparison with a known-good positive control;
- metamorphic relations or invariants across transformed inputs;
- a self-authored conformance check whose coupling and limited claim are explicit;
- informed human judgment when the intended behavior is informal or irreducibly experiential.

The software-testing literature calls difficulty in determining correct behavior the test-oracle problem and documents specifications, models, metamorphic testing, and human domain knowledge as complementary oracle sources:

- https://discovery.ucl.ac.uk/id/eprint/1471263/

## Discriminating tests

Confirmation is often cheap because many competing hypotheses predict the same observation. Prefer evidence that differs across plausible explanations.

For each material hypothesis, record compactly:

- its distinctive prediction;
- the strongest plausible alternative;
- an observation expected under one but not the other;
- a positive control that validates the test path;
- a negative or off-nominal case where relevant;
- the result that would cause abandonment, revision, or reduced confidence.

Wason's hypothesis-testing experiments illustrate how seeking compatible examples without attempting elimination can preserve incorrect rules:

- https://journals.sagepub.com/doi/10.1080/17470216008416717

Do not invert confirmation bias into falsification theater. A surprising result may expose an invalid test environment, noisy measurement, hidden condition, or overly broad prediction. It weighs against the exact tested claim; it does not automatically prove a rival.

## Precommitment and test integrity

Before observing the outcome:

- state the hypothesis and predicted observable result;
- define the acceptance boundary and failure interpretation;
- identify the artifact, inputs, environment, and version under test;
- freeze or record the test and oracle so they cannot silently move with the result;
- define stop, rollback, and escalation conditions.

After observing the outcome:

- preserve raw observations before interpretation;
- compare against the precommitted prediction;
- report deviations and missing coverage;
- change the model before changing the criterion;
- if the criterion was genuinely defective, explain why using evidence independent of the disappointing result, version the new criterion, and rerun the test.

## Proportionate red-team check

Red teaming should improve information quality, not reward contrarian performance. Challenge assumptions most when they are consequential, weakly supported, time-sensitive, load-bearing, or shared by multiple safeguards.

Ask:

- Which explicit or implicit assumption carries the conclusion?
- What is its confidence and evidence provenance?
- Could it have been true elsewhere or earlier but not here and now?
- What condition would invalidate it?
- Are several apparent safeguards actually dependent on the same assumption or data source?
- Is the evidence missing because nothing happened, or because the system cannot observe it?

The UK Ministry of Defence Red Teaming Handbook recommends quality-of-information checks and assumption review, including confidence, supporting evidence, time sensitivity, and invalidating conditions:

- https://www.gov.uk/government/publications/a-guide-to-red-teaming

## Calibrated stopping

Stop adding methods when new analysis is unlikely to discriminate among live alternatives. Continue gathering evidence when a decision depends on an unobserved success surface, an invalid test path, or a load-bearing assumption with no credible check.

Use these terminal labels accurately:

- **Conforms:** specified structural or process requirements passed.
- **Observed:** the stated behavior occurred in the recorded context.
- **Corroborated:** multiple meaningfully different evidence sources agree.
- **Validated for scope:** predefined intended-use criteria passed within named boundaries.
- **Unverified:** the required success surface has not been observed.
- **Disconfirmed for scope:** the predefined prediction failed within a valid test context.

Reproducibility strengthens confidence but is not infallibility; one failed replication can reveal either a false claim or previously uncontrolled conditions. Preserve those alternatives until evidence distinguishes them:

- https://www.nationalacademies.org/read/25303/chapter/1
