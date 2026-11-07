"""Text-level traps for a bridge numeric profile: what the frame decoder takes and refuses, whatever the tool."""
import json


def lexical(tool, good, integer_path):
    text = json.dumps(good, separators=(",", ":"))
    head, key, tail = integer_path
    spliced = lambda token: text.replace(key, head + token + tail, 1)
    out = [text, " " + text + " ", text.replace(":", ": ").replace(",", " ,\t"), text + "x", text + " 1", text[:-1], "", " ", "null", "true", "1", "-0", '"text"', "[]", "[1]", "{}",
           "{" + '"a":1,"a":2' + "}", text[:-1] + ',"__proto__":1}', text[:-1] + ',"constructor":1}', text[:-1] + ',"\\u0061":1}', text[:-1] + ',"café":1}', text[:-1] + '," ":1}',
           text[:-1] + ',"\\ud83d\\ude00":1}', text[:-1] + ',"\\ud83d":1}', text[:-1] + ',"a\\nb":1}', text[:-1] + ',"it\'s":1}', text[:-1] + ',"q\\"\'":1}', text[:-1] + ',"back\\\\slash":1}',
           text[:-1] + ',"\\/\\b\\f\\r\\t":1}', text[:-1] + ',"\x7f":1}', text[:-1] + ',"bad\\x":1}', text[:-1] + ',"raw\ttab":1}', text[:-1] + ',"1":1,"0":2}', text[:-1] + ',"' + "k" * 1024 + '":1}',
           text[:-1] + ',"' + "k" * 1025 + '":1}', text[:-1] + ',"z":' + "[" * 28 + "]" * 28 + "}", text[:-1] + ',"z":' + "[" * 29 + "]" * 29 + "}", text[:-1] + ',"z":' + "[" * 30 + "]" * 30 + "}",
           text[:-1] + ',"z":' + "[" * 40 + "]" * 40 + "}", text[:-1] + ',"z":[' + ",".join(["0"] * 15000) + "]}", text[:-1] + ',"z":[' + ",".join(["0"] * 17000) + "]}",
           text[:-1] + ',"z":"' + "x" * 66000 + '"}', "NaN", "Infinity", "-Infinity", text[:-1] + ',"z":NaN}', text[:-1] + ',"z":-Infinity}']
    for token in ("-0", "0", "1", "-1", "00", "01", "-", "+1", "1.", ".5", "1.0", "1.5", "-0.0", "1e3", "1E3", "1e400", "-1e400", "0.0", "1e-1", "999999999999999", "-999999999999999", "1000000000000000",
                  "1000000000000", "1000000000001", "-1000000000000", "-1000000000001", "86400000", "86400001", "1000", "1001", "9" * 15, "9" * 16, "9" * 450, "-" + "9" * 450, "1" + "0" * 450, "9007199254740993",
                  "true", "false", "null", '"1"', "[]", "{}"):
        out.append(spliced(token))
    return [(tool, t) for t in out] + [("no_such_tool", text), (tool + " ", text)]
