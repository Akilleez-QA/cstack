"""Separate exact input/output JSON profiles for the existing Math protocol."""
import json


class WireFailure(ValueError):
    pass


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise WireFailure("Duplicate JSON keys")
        result[key] = value
    return result


def _no_float(_):
    raise WireFailure("Floating or nonfinite numbers are outside the Math profile")


def _input_integer(token):
    if len(token.lstrip("-")) > 1234:
        raise WireFailure("Input integer token exceeds Math bridge budget")
    value = int(token)
    if value.bit_length() > 4096:
        raise WireFailure("Input integer exceeds Math bridge budget")
    return value


def decode(raw: bytes, *, response=False, parse_float=_no_float):
    byte_cap, depth_cap, node_cap, string_cap = ((1_048_576, 160, 250_000, 1_048_576) if response
                                               else (65_536, 80, 16_384, 4096))
    if type(raw) is not bytes or len(raw) > byte_cap:
        raise WireFailure("Frame byte budget exceeded")
    try:
        text = raw.decode("utf-8", errors="strict")
        depth, quoted, escaped = 0, False, False
        for char in text:
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char in "[{":
                depth += 1
                if depth > depth_cap:
                    raise WireFailure("JSON depth budget exceeded")
            elif char in "]}":
                depth -= 1
        value = json.loads(text, object_pairs_hook=_unique, parse_float=parse_float,
                           parse_constant=_no_float, parse_int=int if response else _input_integer)
    except (ValueError, UnicodeError, RecursionError, OverflowError):
        raise WireFailure("Invalid or over-budget exact JSON frame") from None
    stack, nodes = [value], 0
    while stack:
        item = stack.pop()
        nodes += 1
        if nodes > node_cap:
            raise WireFailure("JSON node budget exceeded")
        if type(item) is dict:
            stack.extend(item.keys())
            stack.extend(item.values())
        elif type(item) is list:
            stack.extend(item)
        elif type(item) is str and len(item) > string_cap:
            raise WireFailure("JSON string budget exceeded")
    return value


def encode(value):
    try:
        return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True,
                          separators=(",", ":")).encode("ascii")
    except (ValueError, TypeError, RecursionError, OverflowError):
        raise WireFailure("Unrepresentable JSON frame") from None

