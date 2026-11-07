import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { sha256 } from './common.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const repository = join(here, '../../..');
const loaded = new Map();

function verifyPin(kernelEntry) {
  const pin = JSON.parse(readFileSync(join(repository, 'contracts/SOURCE-PINS.json'), 'utf8'))[kernelEntry.pin];
  if (!pin) throw new Error(`no source pin for ${kernelEntry.pin}`);
  const root = join(repository, pin.root);
  const raw = readFileSync(join(root, 'SOURCE-MANIFEST.json'));
  if (sha256(raw) !== pin.source_manifest_sha256) throw new Error(`${kernelEntry.pin} manifest differs from its pin`);
  const { files } = JSON.parse(raw);
  for (const [name, expected] of Object.entries(files)) {
    if (name.startsWith(`${kernelEntry.package}/`) && sha256(readFileSync(join(root, name))) !== expected) {
      throw new Error(`${kernelEntry.pin} file differs from its manifest: ${name}`);
    }
  }
  return { root, sourceManifestSha256: pin.source_manifest_sha256 };
}

export async function loadFoundation(id) {
  if (loaded.has(id)) return loaded.get(id);
  const entry = JSON.parse(readFileSync(join(here, 'MANIFEST.json'), 'utf8')).kernels[id];
  if (!entry) return null;
  const { root, sourceManifestSha256 } = verifyPin(entry);
  const source = readFileSync(join(here, entry.module));
  const common = readFileSync(join(here, 'common.mjs'));
  const shared = Object.fromEntries((entry.shared ?? []).map(name => [name, sha256(readFileSync(join(here, name)))]));
  const { createKernel } = await import(pathToFileURL(join(here, entry.module)).href);
  const kernel = createKernel({ root });
  const identity = { foundation: id, version: kernel.version, route: entry.route, source_manifest_sha256: sourceManifestSha256,
    port_sha256: sha256(source), common_sha256: sha256(common), ...(entry.shared ? { shared_sha256: shared } : {}), ...(kernel.projections ? { projections: kernel.projections } : {}), ...(kernel.numeric_tolerance ? { numeric_tolerance: kernel.numeric_tolerance } : {}) };
  const foundation = { ...kernel, identity };
  loaded.set(id, foundation);
  return foundation;
}

export const knownFoundations = () => Object.keys(JSON.parse(readFileSync(join(here, 'MANIFEST.json'), 'utf8')).kernels);
