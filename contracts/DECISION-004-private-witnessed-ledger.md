# Witnessed ledger

`adapters/ledger.py` supplies signed hash chains and quorum checkpoints. `adapters/witnessed_ledger.py` maps them to the core LedgerPort. Configure writer identities, witness public keys and the quorum outside the repository. Private keys are never repository inputs.

Authorization can require a witnessed intent before an effect. Missing or invalid signatures, chains, ownership or checkpoints deny authorization. Hashes alone do not authenticate events.
