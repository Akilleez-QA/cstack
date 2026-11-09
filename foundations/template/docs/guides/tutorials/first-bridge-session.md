# Tutorial: your first bridge session

This tutorial starts the bridge, initializes it, calls the placeholder tool once successfully and once with a bad argument, and reads both receipts. It needs only Python 3.11 or newer. The commands and output below were run at commit `fb9993c` on Linux with CPython 3.14.

## 1. Get the code and check it works

```sh
git clone https://github.com/Akilleez-QA/foundation-template
cd foundation-template
python3 -B -m unittest discover -s tests -t .
```

The last line of the test output should be `OK`.

## 2. Run a session

The bridge reads one JSON-RPC request per line on stdin and writes one response per line on stdout. The first request must be `initialize`. From the repository root:

```sh
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"foundation-template-jsonrpc/1"}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"echo_observation","arguments":{"observation":"reading 7"}}}' \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"echo_observation","arguments":{"observation":""}}}' \
  | python3 -B -m foundation_template_bridge \
  | python3 -c '
import json, sys
for line in sys.stdin:
    reply = json.loads(line)["result"]
    if "protocolVersion" in reply:
        print("initialized:", reply["protocolVersion"], "mcpCompatible:", reply["mcpCompatible"])
        continue
    content = reply["structuredContent"]
    receipt = content["receipt"]
    print(content["assessment"], "isError:", reply["isError"], "result:", receipt["result"], "error:", receipt["error"])
    print("  boundary:", receipt["boundary"])
    print("  evidence:", [entry["evidence"]["basis"]["note"] for entry in receipt["evidence"]])
'
```

Output:

```text
initialized: foundation-template-jsonrpc/1 mcpCompatible: False
observation_echoed isError: False result: {'observation': 'reading 7'} error: None
  boundary: {'control_action': False, 'domain_determination': False, 'observation_only': True}
  evidence: ["Placeholder echo of the caller's own input; no domain source backs it."]
tool_error isError: True result: None error: observation must be a string of 1 to 256 characters
  boundary: {'control_action': False, 'domain_determination': False, 'observation_only': True}
  evidence: ['Argument check by the template Foundation; the request was not observed.']
```

## 3. What to notice

- Both calls return a normal JSON-RPC result. The second is a tool error: `isError` is true and `result` is null, but it still carries Evidence saying which check refused it.
- The `boundary` is the same on every receipt: an observation, never a determination or a control action.
- Each receipt also has `input_sha256`, so a host can bind the result to the exact request.
- The bridge exits 0 when stdin closes.

## 4. Next steps

- Start your own Foundation: [Start a new Foundation](../how-to/start-a-new-foundation.md).
- Every tool, argument and error code: [tool catalog](../reference/tool-catalog.md).
- The protocol: [interface control document](../../icd/icd-cstack.md).
