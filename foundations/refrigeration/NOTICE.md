Copyright © 2026 Refrigeration.AI.

Licensed GPL-3.0-only. If you want to use it to create a product or service under different terms, commercial licenses are available from Refrigeration.AI. Contact craig@nh3.biz.

## Third-party components

No third-party code is shipped or vendored. The runtime uses only the Python standard library (PSF License).

| Component | Use | License |
|---|---|---|
| CoolProp 8.0.0 | Used offline to generate the saturation tables in `foundation_refrigeration/data/` and the points in `golden/`. Not shipped and not imported at runtime | MIT |

Exposure limits and regulatory thresholds in `foundation_refrigeration/data/` are short quotations of public sources (OSHA, NIOSH, ACGIH, eCFR), cited with URL and retrieval date in each record.
