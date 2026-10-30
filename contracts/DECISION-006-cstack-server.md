# Host read models and relay

`adapters/host_read_models.py` projects configured local sources with confidence and freshness. Supply paths and command runners for your environment.

`adapters/relay_outbox.py` stores bounded relay intents. An intent does not confer authority; execution remains subject to host policy and human approval.
