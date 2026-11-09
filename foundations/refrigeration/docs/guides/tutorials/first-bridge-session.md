# Tutorial: your first bridge session

This tutorial starts the bridge, initializes it, asks for one saturation pressure and reads the receipt. It then shows a refused request and how to fix it. It takes about five minutes and needs only Python 3.11 or newer. Every command and output below was run at commit `62764c7` on Linux with CPython 3.14.

## 1. Get the code and check it works

```sh
git clone https://github.com/Akilleez-QA/foundation-refrigeration
cd foundation-refrigeration
python3 -B -m unittest discover -s tests -t .
```

The last line of the test output should be `OK`. Nothing is installed; the code runs from the checkout.

## 2. Ask for the saturation pressure of ammonia at 20 degF

The bridge reads one JSON-RPC request per line on stdin and writes one response per line on stdout. The first request must be `initialize`. Run this from the repository root:

```sh
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"foundation-refrigeration-jsonrpc/1"}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"saturation_pressure","arguments":{"fluid":"ammonia","temperature":{"value":20,"unit":"degF"}}}}' \
  | python3 -B -m foundation_refrigeration_bridge \
  | python3 -c '
import json, sys
for line in sys.stdin:
    reply = json.loads(line)["result"]
    if "protocolVersion" in reply:
        print("initialized:", reply["protocolVersion"], reply["serverInfo"]["version"])
        continue
    receipt = reply["structuredContent"]["receipt"]
    print("status:", receipt["status"])
    for view in receipt["result"]["pressure_views"]:
        print("  %(value)s %(unit)s" % view)
    print("atmosphere:", receipt["result"]["atmosphere"])
    print("evidence:", [entry["applies_to"] for entry in receipt["evidence"]])
'
```

Output:

```text
initialized: foundation-refrigeration-jsonrpc/1 0.1.0
status: success
  332.197 kPa(a)
  230.872 kPa(g)
  48.1811 psia
  33.4852 psig
  3.322 bar(a)
  2.3087 bar(g)
atmosphere: {'assumed': True, 'basis': 'standard', 'pressure': {'unit': 'kPa(a)', 'value': 101.325}}
evidence: ['saturation table NH3', 'units: temperature_scales', 'units: psi_definition', 'units: standard_atmosphere']
```

What to notice:

- The temperature is a `{value, unit}` object. A bare number is refused.
- No atmosphere was given, so the gauge views use the standard atmosphere and the receipt says `assumed: True`.
- Every value has Evidence. The table entry says where the saturation data came from (CoolProp 8.0.0, status CHECK).
- The bridge exits when stdin closes.

## 3. See a refused request, then fix it

R404A is a blend, so it has different bubble and dew temperatures at the same pressure. The bridge will not guess which one you mean:

```sh
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"foundation-refrigeration-jsonrpc/1"}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"saturation_temperature","arguments":{"fluid":"R404A","pressure":{"value":50,"unit":"psig"}}}}' \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"saturation_temperature","arguments":{"fluid":"R404A","pressure":{"value":50,"unit":"psig"},"side":"dew","atmosphere":{"basis":"elevation","elevation":{"value":1600,"unit":"m"}}}}}' \
  | python3 -B -m foundation_refrigeration_bridge \
  | python3 -c '
import json, sys
for line in sys.stdin:
    reply = json.loads(line)["result"]
    if "protocolVersion" in reply:
        continue
    receipt = reply["structuredContent"]["receipt"]
    if reply["isError"]:
        print("error:", receipt["error"]["code"], "-", receipt["error"]["message"])
    else:
        result = receipt["result"]
        print("dew temperature:", result["temperature"], "at", result["pressure_absolute"])
        print("atmosphere:", result["atmosphere"])
'
```

Output:

```text
error: side_required - R404A is a zeotropic blend: give side bubble or dew
dew temperature: {'unit': 'degC', 'value': -10.1678} at {'unit': 'kPa(a)', 'value': 428.2614}
atmosphere: {'assumed': False, 'basis': 'elevation', 'elevation_m': 1600.0, 'pressure': {'unit': 'kPa(a)', 'value': 83.5235}}
```

The first call is a tool error: `isError` is true, the result is null and there is no Evidence. The second call names the side and gives the site elevation, so 50 psig is converted with a 1600 m atmosphere (83.5 kPa) instead of the standard one.

## 4. What you learned and where to go next

- A session is `initialize`, then `tools/call` requests, then close stdin.
- Results are observations with Evidence and a fixed boundary: never an engineering, safety or compliance determination. Read [Limitations and safety-relevant use](../explanation/limitations.md) before using any number.
- Every tool and argument is listed in the [tool catalog](../reference/tool-catalog.md).
- The protocol is specified in the [interface control document](../../icd/icd-cstack.md).
