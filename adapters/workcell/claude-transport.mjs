import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createInterface } from 'node:readline';

const passedEnvironment = ['PATH', 'HOME', 'LANG', 'LC_ALL', 'TERM', 'USER', 'XDG_RUNTIME_DIR', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME'];
const system = 'You write source code. You have no tools and no files. Reply with the complete source file only, with no explanation and no Markdown fences.';
const model = process.env.CSTACK_CLAUDE_MODEL || 'opus';
const command = process.env.CSTACK_CLAUDE_COMMAND || 'claude';
const timeoutMs = Number(process.env.CSTACK_CLAUDE_TIMEOUT_MS) || 300000;
const args = ['-p', '--tools', '', '--no-session-persistence', '--strict-mcp-config', '--setting-sources', '', '--permission-mode', 'dontAsk',
  '--safe-mode', '--disable-slash-commands', '--model', model, '--system-prompt', system, '--output-format', 'stream-json', '--verbose'];

function environment() {
  const env = Object.fromEntries(passedEnvironment.filter(name => process.env[name] !== undefined).map(name => [name, process.env[name]]));
  if (process.env.CSTACK_CLAUDE_CONFIG_DIR) env.CLAUDE_CONFIG_DIR = process.env.CSTACK_CLAUDE_CONFIG_DIR;
  env.CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = '1';
  return env;
}

export function generate(prompt) {
  const cwd = mkdtempSync(join(tmpdir(), 'cstack-claude-'));
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd, env: environment(), stdio: ['pipe', 'pipe', 'ignore'], timeout: timeoutMs });
    let init = null, result = null;
    createInterface({ input: child.stdout }).on('line', line => {
      let event;
      try { event = JSON.parse(line); } catch { return; }
      if (event.type === 'system' && event.subtype === 'init') init = event;
      if (event.type === 'result') result = event;
    });
    child.on('error', reject);
    child.stdin.on('error', () => {});
    child.stdin.end(prompt.text);
    child.on('close', code => {
      rmSync(cwd, { recursive: true, force: true });
      try {
        if (!init || init.apiKeySource !== 'none' || init.tools?.length || init.mcp_servers?.length) throw new Error('transport is not a tool-free subscription session');
        if (code || !result || result.is_error || typeof result.result !== 'string') throw new Error('transport refused the turn');
        resolve({ text: result.result, model: { identity: `claude-code:${init.model}`, version: String(init.claude_code_version ?? 'unknown') } });
      } catch (error) { reject(error); }
    });
  });
}
