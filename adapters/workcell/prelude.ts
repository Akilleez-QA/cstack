@external("kernel", "event_size") declare function event_size(): i32;
@external("kernel", "event_read") declare function event_read(destination: usize): void;
@external("kernel", "emit") declare function emit_bytes(source: usize, length: i32): void;
@external("kernel", "result_size") declare function result_size(handle: i32): i32;
@external("kernel", "result_read") declare function result_read(handle: i32, destination: usize): void;
@external("foundation_refrigeration", "call") declare function refrigeration_call(tool: usize, toolLength: i32, args: usize, argsLength: i32): i32;
@external("foundation_template", "call") declare function template_call(tool: usize, toolLength: i32, args: usize, argsLength: i32): i32;
@external("foundation_math", "call") declare function math_call(tool: usize, toolLength: i32, args: usize, argsLength: i32): i32;
@external("foundation_film", "call") declare function film_call(tool: usize, toolLength: i32, args: usize, argsLength: i32): i32;
@external("foundation_robotics", "call") declare function robotics_call(tool: usize, toolLength: i32, args: usize, argsLength: i32): i32;

function utf8(text: string): ArrayBuffer { return String.UTF8.encode(text); }

function fromHost(size: i32, handle: i32): string {
  const buffer = new ArrayBuffer(size);
  if (handle < 0) event_read(changetype<usize>(buffer));
  else result_read(handle, changetype<usize>(buffer));
  return String.UTF8.decode(buffer);
}

export function event(): string { return fromHost(event_size(), -1); }

export function emit(transition: string): void {
  const bytes = utf8(transition);
  emit_bytes(changetype<usize>(bytes), bytes.byteLength);
}

function answer(handle: i32): string {
  if (handle < 0) return "{\"refused\":true}";
  return fromHost(result_size(handle), handle);
}

export function refrigeration(tool: string, args: string): string {
  const t = utf8(tool), a = utf8(args);
  return answer(refrigeration_call(changetype<usize>(t), t.byteLength, changetype<usize>(a), a.byteLength));
}

export function template(tool: string, args: string): string {
  const t = utf8(tool), a = utf8(args);
  return answer(template_call(changetype<usize>(t), t.byteLength, changetype<usize>(a), a.byteLength));
}

export function math(tool: string, args: string): string {
  const t = utf8(tool), a = utf8(args);
  return answer(math_call(changetype<usize>(t), t.byteLength, changetype<usize>(a), a.byteLength));
}

export function film(tool: string, args: string): string {
  const t = utf8(tool), a = utf8(args);
  return answer(film_call(changetype<usize>(t), t.byteLength, changetype<usize>(a), a.byteLength));
}

export function robotics(tool: string, args: string): string {
  const t = utf8(tool), a = utf8(args);
  return answer(robotics_call(changetype<usize>(t), t.byteLength, changetype<usize>(a), a.byteLength));
}

function skipValue(text: string, start: i32): i32 {
  let at = start;
  while (text.charCodeAt(at) <= 32) at++;
  const first = text.charCodeAt(at);
  if (first == 34) {
    at++;
    while (text.charCodeAt(at) != 34) at += text.charCodeAt(at) == 92 ? 2 : 1;
    return at + 1;
  }
  if (first == 123 || first == 91) {
    let depth = 0;
    let quoted = false;
    for (; at < text.length; at++) {
      const c = text.charCodeAt(at);
      if (quoted) {
        if (c == 92) at++;
        else if (c == 34) quoted = false;
      } else if (c == 34) quoted = true;
      else if (c == 123 || c == 91) depth++;
      else if (c == 125 || c == 93) {
        depth--;
        if (depth == 0) return at + 1;
      }
    }
    return at;
  }
  while (at < text.length) {
    const c = text.charCodeAt(at);
    if (c == 44 || c == 125 || c == 93 || c <= 32) break;
    at++;
  }
  return at;
}

export function field(json: string, path: string): string {
  let text = json;
  const names = path.split(".");
  for (let i = 0; i < names.length; i++) {
    const name = "\"" + names[i] + "\"";
    let at = 1;
    let found = false;
    while (at < text.length) {
      while (at < text.length && (text.charCodeAt(at) <= 32 || text.charCodeAt(at) == 44)) at++;
      if (text.charCodeAt(at) != 34) break;
      const end = skipValue(text, at);
      const key = text.substring(at, end);
      at = end;
      while (text.charCodeAt(at) <= 32 || text.charCodeAt(at) == 58) at++;
      const valueEnd = skipValue(text, at);
      if (key == name) {
        text = text.substring(at, valueEnd);
        found = true;
        break;
      }
      at = valueEnd;
    }
    if (!found) return "null";
  }
  return text;
}
