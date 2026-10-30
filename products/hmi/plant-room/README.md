# Plant room: cstack, operated like a plant

The first cockpit on the cstack server (ADR 005 item 8c, DECISION-006): the fleet drawn as a refrigeration plant
(Refrigeration.AI brand), every section reading a live read model. Workers, the GPU queue and safety guard, fleet
capacity, the heavy-run throttle and memguard, agent sessions, the Codex pool, Endoforge conductor jobs, the merge
train, POODO's state root, this machine's resources (CPU load, memory, swap, GPU use, VRAM, BAR1, disks) and the work
running now (GPU jobs running or waiting, processes on the GPU, heavy-run jobs, process families by memory) each
arrive as a projection that cites its source, as-of time and confidence.
`PLANT-CONNECT.md` maps each plant section to its read model and to the controls it would carry.

## Run it (read-only)

```bash
python -B tools/cstack_server.py
```

Run it from the repository root. Open http://127.0.0.1:4380. Drag to orbit, scroll to zoom, click a section for its live
readings. The page follows the server's stream and resumes after the last sequence it saw. Without the server it plays
`snapshot.json` (a redacted capture) and says so.

Without WebGL (the Claude desktop app's browser pane runs with hardware acceleration off, and so has none), or when the
3D code cannot load, the page shows `plant.jpg`, a Cycles render of the same plant, instead. Drag to pan, scroll or use
the buttons to zoom, double-click to fit. Each section has a live marker (green fresh, amber partial, grey stale; a
pulse when it is busy) that opens the same card, and the poster's labels appear once zoomed in.

## Live layer and interactivity (no WebGL)

Over the rendered plant, `fx.js` draws a live layer on a 2D canvas from the same projections: pulses along every visible
conduit (intent while sessions are live, work in progress while GPU or heavy jobs or lanes run, verified builds after a
merge, interlocks flashing on shields up), the GPU fins lit by GPU use, a capacity arc on the dial, packets on active
lanes, envelopes in the fleet tube, a pod lit per live session, the POODO check chase, a radar at the remote site and a
scan line across the deck. Hover a building for its outline and live reading; click it for its card. The layer's data
comes from the same Blender build as the picture (`build_plant.py --overlay`, then `overlay_assets.py`), so it lands
exactly on the buildings.

## Relay to the teams

The rail's relay console sends the owner's message to a team, or lets the orchestrator decide. The server puts it in the
relay outbox (`POST /api/relay`, guarded); the relay agent session (`RELAY.md`) delivers it and carries replies back,
and the console shows each message's state. Approvals still go in the session itself.

Teams are the Claude Code sessions the agent can reach, plus two that are not sessions and never go through fleet mail:
**Codex** (`codex exec` through codex-pool, read-only; its team entry shows when a usage limit lifts) and **Grok Bot**
on the Grok box (a mailbox the box pulls through its existing snapshot gate every minute; `workshop/box/relay`).

## Files

| File | What |
|---|---|
| `index.html` | The cockpit: three.js 0.160 from jsDelivr, the plant model, live HUD (mode, gauges with fresh and stale dots, every projection's confidence), motion driven by state, section cards. |
| `plant.glb`, `plant.anchors.json` | The plant model and its label anchors, exported from the Blender build (`build_plant.py --glb`). |
| `fx.js`, `overlay.json`, `sections-id.png`, `section-*.png` | The live layer over the rendered plant: flows, moving parts and section outlines in plate pixels. |
| `relay.js`, `RELAY.md` | The relay console, and the relay agent's protocol. |
| `plant.jpg`, `plant.labels.json` | The rendered plant for browsers without WebGL (`run_draft.sh cockpit --res 2560x1440 --samples 128`) and its labels as percentages of the picture. |
| `snapshot.json` | A redacted capture of the server's snapshot for the offline page. |
| `PLANT-CONNECT.md` | The connection map: section, read model, control, and the T3 Code capability each one ports. |

## Safety

The server binds to loopback and writes one thing: the owner's relay messages, through the guarded `POST /api/relay` into the relay outbox (DECISION-006 decision 4). The read models run only allowlisted read commands. They never
run `gpu-queue.py --stats`, which deletes stale tickets, or `codex-pool`, which launches codex. From session files they
read only a whitelist of fields. Controls are listed per section with their class (operator, or STOP / APPROVE / MERGE
for the owner) and none is armed. Approvals never pass through an HMI (ADR 005 decision 5).
