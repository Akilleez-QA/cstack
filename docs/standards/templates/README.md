# Templates

Skeletons for `family-doc-standard.md`. Copy a template to its destination, replace every `<...>`, fill each heading with real content (or replace it with a one-line tailoring note), and delete all HTML guidance comments. Issue and PR templates are the exception: their comments stay, because GitHub does not render them.

| Template | Destination | SWEHB / SWE | Required for |
|---|---|---|---|
| docs-index.md | `docs/README.md` | — | all |
| software-management-plan.md | `docs/plan/software-management-plan.md` | 5.08, 5.04, 5.17, 5.27, 5.15 decision | all |
| compliance-matrix.md | `docs/plan/compliance-matrix.md` | 7.16, SWE-125 | all |
| requirements.md | `docs/requirements/requirements.md` | 5.09 | all |
| architecture.md | `docs/architecture/architecture.md` | 5.13 | all |
| icd.md | `docs/icd/icd-<name>.md` | 5.02 | all (one per external interface) |
| data-dictionary.md | `docs/data/data-dictionary.md` | 5.07 | H E F T; S minimal |
| test-plan.md | `docs/verification/test-plan.md` | 5.10, 5.14 | all |
| verification-matrix.md | `docs/verification/verification-matrix.md` | SWE-052 | all |
| test-report.md | `docs/verification/reports/STR-<tag>.md` | 5.11, 5.05 | all, per release |
| configuration-management.md | `docs/configuration/configuration-management.md` | 5.06 | all |
| version-description.md | `docs/releases/VDD-<tag>.md` | 5.16 | all, per release |
| assurance-record.md | `docs/assurance/assurance-record.md` | 5.21, 5.22, 5.23, 5.25, 5.26, 5.03 | all |
| user-manual-map.md | `docs/guides/SUM-MAP.md` | 5.12 | all |
| limitations.md | `docs/guides/explanation/limitations.md` | 5.24 substitute | refrigeration, robotics; recommended host |
| problem-report.md | `.github/ISSUE_TEMPLATE/problem-report.md` | 5.01 | all |
| change-request.md | `.github/ISSUE_TEMPLATE/change-request.md` | 5.01 | all |
| pull-request.md | `.github/pull_request_template.md` | 5.03 | all |

Where a repo already has the document (for example cstack's `requirements.md` or `configuration-management.md`), keep its content and IDs. Add the missing headings, metadata header and change history. Do not replace the document with the skeleton.
