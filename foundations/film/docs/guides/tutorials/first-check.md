# Tutorial: your first film check

This tutorial starts the bridge, asks `drift_verdict` to judge two short clips, and reads the receipts. It takes about five minutes. You need Python 3.11 or newer and a clone of this repository; nothing is installed.

## 1. Run the tests

From the repository root:

```sh
python -B -m unittest discover -s tests -t .
```

The last line should be `OK (skipped=4)`. The four skipped tests need the optional video libraries; see the [how-to guides](../how-to/README.md#run-the-optional-producer-tests).

## 2. Write a session

The bridge reads one JSON-RPC message per line on stdin. The first message must be `initialize`. The next three call `drift_verdict` with per-frame edge F1 and mask IoU in milli-units (980 means 0.980): a clip that collapses at its last frame, a clip that holds, and a value out of range.

Run this block from the repository root:

```sh
cat > session.jsonl <<'JSON'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"foundation-film-jsonrpc/1"}}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"drift_verdict","arguments":{"frames":{"edge_f1":[980,700,80],"mask_iou":[840,700,0]}}}}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"drift_verdict","arguments":{"frames":{"edge_f1":[980,900,850],"mask_iou":[840,800,790]}}}}
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"drift_verdict","arguments":{"frames":{"edge_f1":[1001]}}}}
JSON
python -B -m foundation_film_bridge < session.jsonl > replies.jsonl
echo "exit status $?"
python -B -c '
import json
for line in open("replies.jsonl"):
    reply = json.loads(line)["result"]
    if "protocolVersion" in reply:
        print("handshake", reply["protocolVersion"], "mcpCompatible", reply["mcpCompatible"])
        continue
    content = reply["structuredContent"]
    receipt = content["receipt"]
    result = receipt["result"] or {}
    print(content["assessment"], "first failing frame", result.get("first_failing_frame"),
          receipt["error"], len(receipt["evidence"]), "evidence", receipt["input_sha256"][:12])
'
rm session.jsonl replies.jsonl
```

Expected output (run at the documented baseline):

```
exit status 0
handshake foundation-film-jsonrpc/1 mcpCompatible False
thresholds_not_met first failing frame 2 None 3 evidence e4efdb26e3e9
thresholds_met first failing frame None None 3 evidence 44e60bb53975
tool_error first failing frame None frames.edge_f1[0] must be an integer from 0 to 1000 1 evidence 0e0559e18109
```

## 3. Read the results

- The handshake names the protocol and says the bridge is not an MCP server.
- The first clip fails at frame 2, where edge F1 is 0.080 and mask IoU 0.000. The default thresholds are 0.450 and 0.600. The gate is the worst frame, so a good average does not save it.
- The second clip stays above both thresholds on every frame, so it meets them.
- The third request is refused: `isError` is true, the assessment is `tool_error`, the result is null, and there is still one Evidence entry.
- Every receipt carries `input_sha256`, the hash of the arguments. The host recomputes it to bind the result to the request.

None of these verdicts is an acceptance decision. Each receipt says so in `boundary`, and the client remains the acceptance authority.

## Next steps

- Field reference for all six tools: [tool catalog](../reference/tool-catalog.md).
- Producing shot measurements from a video: [how-to guides](../how-to/README.md#measure-a-local-video).
- What a pass does and does not mean: [limitations](../explanation/limitations.md).
