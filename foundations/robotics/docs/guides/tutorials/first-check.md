# Tutorial: your first motion check

This tutorial starts the bridge, asks it to judge three squash-and-stretch frames, and reads the receipts. It takes about five minutes. You need Python 3.11 or newer and a clone of this repository; nothing is installed.

## 1. Run the tests

From the repository root:

```sh
python -B -m unittest discover -s tests -t .
```

The last line should be `OK`.

## 2. Write a session

The bridge reads one JSON-RPC message per line on stdin. The first message must be `initialize`. The next three call `squash_check`: a squeeze that grows the volume, a squeeze that keeps it, and an empty request that the tool refuses.

Run this block from the repository root:

```sh
cat > session.jsonl <<'JSON'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"foundation-robotics-jsonrpc/1"}}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"squash_check","arguments":{"frames":[{"scale_permille":[1180,780,1180]}]}}}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"squash_check","arguments":{"frames":[{"scale_permille":[1132,780,1132]}]}}}
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"squash_check","arguments":{"frames":[]}}}
JSON
python -B -m foundation_robotics_bridge < session.jsonl > replies.jsonl
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
    print(content["assessment"], [f["volume_permille"] for f in result.get("frames", [])],
          receipt["error"], len(receipt["evidence"]), "evidence", receipt["input_sha256"][:12])
'
rm session.jsonl replies.jsonl
```

Expected output (run at the documented baseline):

```
exit status 0
handshake foundation-robotics-jsonrpc/1 mcpCompatible False
thresholds_not_met [1086] None 2 evidence 08379c216172
thresholds_met [1000] None 2 evidence d2f493ef76f5
tool_error [] frames must be a list of 1 to 1000 items 1 evidence 2ac0a74c8421
```

## 3. Read the results

- The handshake names the protocol and says the bridge is not an MCP server.
- Scales of 1.180 x 0.780 x 1.180 give a volume of 1.086, 86 permille over constant volume. The default tolerance is 30 permille, so the verdict is `thresholds_not_met`.
- Scales of 1.132 x 0.780 x 1.132 keep the volume at 1.000, so the verdict is `thresholds_met`.
- The empty request is refused: `isError` is true, the assessment is `tool_error`, the result is null, and there is still one Evidence entry.
- Every receipt carries `input_sha256`, the hash of the arguments. The host recomputes it to bind the result to the request.

None of these verdicts is an acceptance decision. Each receipt says so in `boundary`.

## Next steps

- Field reference for all six tools: [tool catalog](../reference/tool-catalog.md).
- Tasks such as overriding a threshold: [how-to guides](../how-to/README.md).
- What the checks cannot tell you: [limitations](../explanation/limitations.md).
