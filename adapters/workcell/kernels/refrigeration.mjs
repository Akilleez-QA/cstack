import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { KernelRefusal, ToolInputError, isObject, keysAre, parseArguments, pyFloat, pyRound, rounded, sha256 } from './common.mjs';

const VERSION = '0.1.0';
const RECEIPT_SCHEMA = 'foundation-refrigeration-receipt/1';
const TOOLS = ['saturation_pressure', 'saturation_temperature', 'convert_pressure', 'convert_temperature',
  'check_reading_against_saturation', 'exposure_limits', 'resolve_equipment_kind'];
const BOUNDARY = { observation_only: true, engineering_determination: false, safety_determination: false,
  compliance_determination: false, diagnosis: false, control_action: false };
const COMMON_LIMITATIONS = [
  'A tool observation is not an engineering, safety or compliance determination.',
  'Monitoring-only: nothing here operates, controls or writes to a plant.',
  'CHECK means recorded but not approved by a qualified person; silence is not approval.',
];
const PLACES = 4;
const ATM = 101.325;
const KPA_PER_PSI = 6.894757293168361;
const KELVIN = 273.15;
const PRESSURE_UNITS = ['kPa(a)', 'kPa(g)', 'psia', 'psig', 'bar(a)', 'bar(g)'];
const TEMPERATURE_UNITS = ['degC', 'degF', 'K', 'degR'];
const GAUGE = ['kPa(g)', 'psig', 'bar(g)'];
const FLUID_FILES = ['nh3', 'co2', 'r134a', 'r290', 'r22', 'r404a', 'r410a', 'r507a', 'r448a'];
const FLUID_ALIASES = { nh3: 'NH3', r717: 'NH3', ammonia: 'NH3', co2: 'CO2', r744: 'CO2', carbondioxide: 'CO2',
  r134a: 'R134a', hfc134a: 'R134a', r290: 'R290', propane: 'R290', r22: 'R22', hcfc22: 'R22',
  r404a: 'R404A', r410a: 'R410A', r507a: 'R507A', r448a: 'R448A' };
const cited = (source, version, clause = null) => ({ basis: { kind: 'cited', source, version, clause }, status: 'CHECK' });
const UNIT_EVIDENCE = {
  standard_atmosphere: cited('CGPM 10th meeting, Resolution 4 (standard atmosphere = 101 325 Pa)', '1954', 'Resolution 4'),
  psi_definition: cited('NIST Special Publication 811, Guide for the Use of the International System of Units (pound-force per square inch from the avoirdupois pound, standard gravity and the inch)', '2008 edition'),
  temperature_scales: cited('NIST Special Publication 811, Guide for the Use of the International System of Units (degC, degF, K and degR relations)', '2008 edition'),
  isa_barometric: cited('ISO 2533 Standard Atmosphere, troposphere barometric formula as ported from the foundation-refr units.ts draft: 101.325 kPa * (1 - 2.25577e-5 * h)^5.25588', '1975'),
  site_measured_atmosphere: { basis: { kind: 'practice', note: 'Caller-supplied site barometric pressure; this Foundation does not verify the reading.' }, status: 'CHECK' },
};
const SUBSTANCES = ['ammonia', 'nh3', 'r717', 'r-717'];
const ISSUERS = ['OSHA', 'NIOSH', 'ACGIH'];
const POLICY_SCOPES = ['plant', 'client', 'expression'];
const PUBLISHED_WORDS = /(?<![A-Za-z0-9_])(osha|niosh|acgih|aiha|cal\/?osha|pel|rel|tlv|idlh|erpg|stel|twa|legal|regulatory|regulation|statutory|law|cfr|limit|limits)(?![A-Za-z0-9_])/i;

class UnitError extends Error {}
class ThermoError extends ToolInputError {}

const has = (list, value) => typeof value === 'string' && list.includes(value);

function finiteNumber(value, name = 'value') {
  if (typeof value !== 'number' || !Number.isFinite(value) || Math.abs(value) > 1e9) throw new UnitError(`${name} must be a finite decimal number`);
  return value;
}

function quantity(value, units, name) {
  if (!isObject(value) || !keysAre(value, ['value', 'unit'])) throw new UnitError(`${name} must be {value, unit}; a bare number is not a quantity`);
  if (!has(units, value.unit)) throw new UnitError(`${name} unit must be one of ${units.join(', ')}`);
  return [finiteNumber(value.value, name), value.unit];
}

function toCelsius(value, unit) {
  const c = unit === 'degC' ? value : unit === 'degF' ? (value - 32) / 1.8 : unit === 'K' ? value - KELVIN : (value / 1.8) - KELVIN;
  if (c + KELVIN <= 0) throw new UnitError('Temperature is at or below absolute zero');
  return c;
}

const fromCelsius = (c, unit) => unit === 'degC' ? c : unit === 'degF' ? c * 1.8 + 32 : unit === 'K' ? c + KELVIN : (c + KELVIN) * 1.8;

function absoluteKpa(value, unit, atmosphere) {
  const kpa = unit === 'kPa(a)' ? value : unit === 'kPa(g)' ? value + atmosphere : unit === 'psia' ? value * KPA_PER_PSI
    : unit === 'psig' ? value * KPA_PER_PSI + atmosphere : unit === 'bar(a)' ? value * 100 : value * 100 + atmosphere;
  if (kpa <= 0) throw new UnitError('Absolute pressure must be positive');
  return kpa;
}

const fromAbsoluteKpa = (kpa, unit, atmosphere) => unit === 'kPa(a)' ? kpa : unit === 'kPa(g)' ? kpa - atmosphere : unit === 'psia' ? kpa / KPA_PER_PSI
  : unit === 'psig' ? (kpa - atmosphere) / KPA_PER_PSI : unit === 'bar(a)' ? kpa / 100 : (kpa - atmosphere) / 100;

function readAtmosphere(value) {
  if (value === null || value === undefined) return [ATM, { basis: 'standard', assumed: true }, ['standard_atmosphere']];
  if (!isObject(value) || !Object.hasOwn(value, 'basis')) throw new UnitError('atmosphere must name its basis');
  const { basis } = value;
  if (basis === 'standard') {
    if (Object.keys(value).length !== 1) throw new UnitError('Standard atmosphere takes no other fields');
    return [ATM, { basis: 'standard', assumed: false }, ['standard_atmosphere']];
  }
  if (basis === 'elevation') {
    if (!keysAre(value, ['basis', 'elevation'])) throw new UnitError('Elevation atmosphere needs exactly an elevation quantity');
    const [number, unit] = quantity(value.elevation, ['m', 'ft'], 'elevation');
    const metres = unit === 'ft' ? number * 0.3048 : number;
    if (!(metres >= -500 && metres <= 6000)) throw new UnitError('Elevation outside the supported -500..6000 m band');
    return [ATM * (1 - 2.25577e-5 * metres) ** 5.25588, { basis: 'elevation', assumed: false, elevation_m: pyRound(metres, 3) }, ['standard_atmosphere', 'isa_barometric']];
  }
  if (basis === 'measured') {
    if (!keysAre(value, ['basis', 'pressure'])) throw new UnitError('Measured atmosphere needs exactly a pressure quantity');
    const [number, unit] = quantity(value.pressure, ['kPa(a)', 'psia', 'bar(a)'], 'atmosphere pressure');
    const kpa = absoluteKpa(number, unit, ATM);
    if (!(kpa >= 40 && kpa <= 110)) throw new UnitError('Measured atmosphere outside the plausible 40..110 kPa band');
    return [kpa, { basis: 'measured', assumed: false }, ['site_measured_atmosphere']];
  }
  throw new UnitError('atmosphere basis must be standard, elevation or measured');
}

const pressureViews = (kpa, atmosphere) => PRESSURE_UNITS.map(unit => ({ value: rounded(fromAbsoluteKpa(kpa, unit, atmosphere), PLACES), unit }));
const temperatureViews = c => TEMPERATURE_UNITS.map(unit => ({ value: rounded(fromCelsius(c, unit), PLACES), unit }));
const ev = (applies_to, evidence) => ({ applies_to, evidence });
const unitEvidence = keys => keys.map(key => ev(`units: ${key}`, UNIT_EVIDENCE[key]));

function fields(args, required, optional = []) {
  if (!isObject(args)) throw new ToolInputError('invalid_arguments', 'Arguments must be an object');
  const keys = Object.keys(args);
  const missing = required.filter(k => !keys.includes(k)).sort();
  const extra = keys.filter(k => !required.includes(k) && !optional.includes(k)).sort();
  if (missing.length || extra.length) throw new ToolInputError('invalid_arguments', `Missing fields: ${missing.join(', ') || 'none'}; unexpected fields: ${extra.join(', ') || 'none'}`);
  return args;
}

const pyStrip = text => text.replace(/^[\s\x1c-\x1f\x85]+|[\s\x1c-\x1f\x85]+$/g, '');

export function createKernel({ root }) {
  const data = {};
  const load = (name, schema) => {
    const raw = readFileSync(join(root, 'foundation_refrigeration/data', name));
    const document = JSON.parse(raw.toString('utf8'));
    if (document.schema !== schema) throw new Error(`projection schema mismatch: ${name}`);
    data[name] = sha256(raw);
    return [document.data, data[name]];
  };
  const tables = {};
  for (const fid of FLUID_FILES) {
    const [table, sha] = load(`refrigerant-saturation.${fid}.json`, 'refrigerant-saturation/1');
    const temps = table.rows.map(r => r[0]);
    tables[table.id] = { id: table.id, name: table.name, kind: table.kind, source: table.source, edition: table.edition,
      minC: temps[0], maxC: temps.at(-1), errorK: table.interpolation.error_k, temps, bubble: table.rows.map(r => r[1]), dew: table.rows.map(r => r[2]),
      evidence: table.evidence, sha, generator: table.generator.sha256, blend: table.kind !== 'pure' };
  }
  const [limitsData, limitsSha] = load('exposure-limits.json', 'exposure-limits/1');
  const [plant, plantSha] = load('plant-taxonomy.json', 'plant-taxonomy/1');
  const [decisions, decisionsSha] = load('open-decisions.json', 'open-decisions/1');
  const kinds = Object.fromEntries(plant.kinds.map(kind => [kind.id, kind]));
  const services = Object.fromEntries(plant.line_services.map(row => [row.code, row]));
  const openDecisions = Object.fromEntries(decisions.decisions.map(item => [item.id, item]));

  const resolveFluid = name => {
    if (typeof name !== 'string' || name.length > 64) throw new ThermoError('unknown_fluid', 'Fluid must be a short name');
    const key = [...name.toLowerCase()].filter(c => !' -_()'.includes(c)).join('');
    if (!Object.hasOwn(FLUID_ALIASES, key)) throw new ThermoError('unknown_fluid', `No generated table for this fluid; supported: ${Object.keys(tables).join(', ')}`);
    return tables[FLUID_ALIASES[key]];
  };
  const side = (table, value) => {
    if (value === null || value === undefined) {
      if (table.blend) throw new ThermoError('side_required', `${table.id} is a zeotropic blend: give side bubble or dew`);
      return 'bubble';
    }
    if (value !== 'bubble' && value !== 'dew') throw new ThermoError('invalid_side', 'side must be bubble or dew');
    return value;
  };
  const x = c => 1 / (c + KELVIN);
  const pressureOf = (table, c, requested) => {
    const chosen = side(table, requested);
    if (!(table.minC <= c && c <= table.maxC)) throw new ThermoError('outside_table_range', `Temperature outside the generated table range ${table.minC.toFixed(4)}..${table.maxC.toFixed(4)} degC`);
    const ps = chosen === 'bubble' ? table.bubble : table.dew, ts = table.temps;
    for (let i = 0; i < ts.length - 1; i++) {
      if (c === ts[i]) return [ps[i], chosen];
      if (ts[i] <= c && c <= ts[i + 1]) {
        if (c === ts[i + 1]) return [ps[i + 1], chosen];
        const x0 = x(ts[i]), x1 = x(ts[i + 1]), y0 = Math.log(ps[i]), y1 = Math.log(ps[i + 1]);
        return [Math.exp(y0 + (y1 - y0) * (x(c) - x0) / (x1 - x0)), chosen];
      }
    }
    throw new ThermoError('outside_table_range', 'Temperature outside the generated table range');
  };
  const temperatureOf = (table, kpa, requested) => {
    const chosen = side(table, requested);
    const ps = chosen === 'bubble' ? table.bubble : table.dew, ts = table.temps;
    if (!(ps[0] <= kpa && kpa <= ps.at(-1))) throw new ThermoError('outside_table_range', `Pressure outside the generated ${chosen} range ${ps[0].toFixed(4)}..${ps.at(-1).toFixed(4)} kPa(a)`);
    const y = Math.log(kpa);
    for (let i = 0; i < ps.length - 1; i++) {
      if (kpa === ps[i]) return [ts[i], chosen];
      if (ps[i] <= kpa && kpa <= ps[i + 1]) {
        if (kpa === ps[i + 1]) return [ts[i + 1], chosen];
        const y0 = Math.log(ps[i]), y1 = Math.log(ps[i + 1]), x0 = x(ts[i]), x1 = x(ts[i + 1]);
        return [1 / (x0 + (x1 - x0) * (y - y0) / (y1 - y0)) - KELVIN, chosen];
      }
    }
    throw new ThermoError('outside_table_range', 'Pressure outside the generated table range');
  };
  const describe = t => ({ id: t.id, name: t.name, kind: t.kind, source: t.source, edition: t.edition, projection_schema: 'refrigerant-saturation/1',
    projection_sha256: t.sha, generator_sha256: t.generator, range_c: [t.minC, t.maxC], interpolation_error_k: t.errorK });
  const tableSource = t => ({ projection: `refrigerant-saturation.${t.id.toLowerCase()}.json`, schema: 'refrigerant-saturation/1', sha256: t.sha, generator_sha256: t.generator });
  const sideLabel = (t, s) => t.blend ? s : 'saturated (pure fluid: bubble equals dew)';
  const atmosphere = args => {
    const [kpa, description, keys] = readAtmosphere(args.atmosphere);
    return [kpa, { ...description, pressure: { value: rounded(kpa, PLACES), unit: 'kPa(a)' } }, keys];
  };

  const tools = {
    saturation_pressure(args) {
      fields(args, ['fluid', 'temperature'], ['side', 'atmosphere']);
      const table = resolveFluid(args.fluid);
      const [value, unit] = quantity(args.temperature, TEMPERATURE_UNITS, 'temperature');
      const c = toCelsius(value, unit);
      const [atm, record, keys] = atmosphere(args);
      const [kpa, chosen] = pressureOf(table, c, args.side);
      return ['saturation_pressure_observed', { fluid: describe(table), side: sideLabel(table, chosen), temperature: { value: rounded(c, 6), unit: 'degC' },
        pressure: { value: rounded(kpa, PLACES), unit: 'kPa(a)' }, pressure_views: pressureViews(kpa, atm), atmosphere: record },
      [ev(`saturation table ${table.id}`, table.evidence), ...unitEvidence(['temperature_scales', 'psi_definition', ...keys])], [tableSource(table)],
      ['Interpolated between generated rows (ln P against 1/T); error bound covers the lookup only.', 'Gauge views use the stated atmosphere; a different site atmosphere changes them.']];
    },
    saturation_temperature(args) {
      fields(args, ['fluid', 'pressure'], ['side', 'atmosphere']);
      const table = resolveFluid(args.fluid);
      const [value, unit] = quantity(args.pressure, PRESSURE_UNITS, 'pressure');
      const [atm, record, keys] = atmosphere(args);
      const kpa = absoluteKpa(value, unit, atm);
      const [c, chosen] = temperatureOf(table, kpa, args.side);
      return ['saturation_temperature_observed', { fluid: describe(table), side: sideLabel(table, chosen), pressure_absolute: { value: rounded(kpa, PLACES), unit: 'kPa(a)' },
        temperature: { value: rounded(c, PLACES), unit: 'degC' }, temperature_views: temperatureViews(c), atmosphere: record, atmosphere_used: GAUGE.includes(unit) },
      [ev(`saturation table ${table.id}`, table.evidence), ...unitEvidence(['temperature_scales', 'psi_definition', ...keys])], [tableSource(table)],
      ['Interpolated between generated rows (ln P against 1/T); error bound covers the lookup only.']];
    },
    convert_pressure(args) {
      fields(args, ['pressure', 'to_unit'], ['atmosphere']);
      const [value, unit] = quantity(args.pressure, PRESSURE_UNITS, 'pressure');
      if (!has(PRESSURE_UNITS, args.to_unit)) throw new ToolInputError('invalid_unit', `to_unit must be one of ${PRESSURE_UNITS.join(', ')}`);
      const [atm, record, keys] = atmosphere(args);
      const kpa = absoluteKpa(value, unit, atm);
      const used = GAUGE.includes(unit) || GAUGE.includes(args.to_unit);
      return ['pressure_converted', { input: { value, unit }, absolute: { value: rounded(kpa, PLACES), unit: 'kPa(a)' },
        output: { value: rounded(fromAbsoluteKpa(kpa, args.to_unit, atm), PLACES), unit: args.to_unit }, atmosphere: record, atmosphere_used: used },
      unitEvidence(['psi_definition', ...(used ? keys : [])]), [], ['A gauge value is relative to the stated atmosphere, not always the standard one.']];
    },
    convert_temperature(args) {
      fields(args, ['temperature', 'to_unit']);
      const [value, unit] = quantity(args.temperature, TEMPERATURE_UNITS, 'temperature');
      if (!has(TEMPERATURE_UNITS, args.to_unit)) throw new ToolInputError('invalid_unit', `to_unit must be one of ${TEMPERATURE_UNITS.join(', ')}`);
      const c = toCelsius(value, unit);
      return ['temperature_converted', { input: { value, unit }, canonical: { value: rounded(c, 6), unit: 'degC' },
        output: { value: rounded(fromCelsius(c, args.to_unit), PLACES), unit: args.to_unit } },
      unitEvidence(['temperature_scales']), [], ['Absolute temperatures only; a temperature difference is not converted by this tool.']];
    },
    check_reading_against_saturation(args) {
      fields(args, ['fluid', 'pressure', 'temperature'], ['atmosphere']);
      const table = resolveFluid(args.fluid);
      const [pValue, pUnit] = quantity(args.pressure, PRESSURE_UNITS, 'pressure');
      const [tValue, tUnit] = quantity(args.temperature, TEMPERATURE_UNITS, 'temperature');
      const [atm, record, keys] = atmosphere(args);
      const kpa = absoluteKpa(pValue, pUnit, atm);
      const c = toCelsius(tValue, tUnit);
      const [dew] = temperatureOf(table, kpa, 'dew');
      const [bubble] = temperatureOf(table, kpa, 'bubble');
      const resolution = table.errorK + 0.0001;
      const aboveDew = c - dew, belowBubble = bubble - c;
      const relation = delta => Math.abs(delta) <= resolution ? 'within_lookup_resolution' : delta > 0 ? 'above' : 'below';
      const delta = k => ({ value_k: rounded(k, PLACES), value_degf_difference: rounded(k * 1.8, PLACES) });
      return ['reading_compared_to_saturation', { fluid: describe(table), reading: { pressure: { value: pValue, unit: pUnit }, temperature: { value: tValue, unit: tUnit } },
        pressure_absolute: { value: rounded(kpa, PLACES), unit: 'kPa(a)' }, temperature: { value: rounded(c, PLACES), unit: 'degC' },
        saturation_at_reading_pressure: { dew_temperature: { value: rounded(dew, PLACES), unit: 'degC' }, bubble_temperature: { value: rounded(bubble, PLACES), unit: 'degC' } },
        superheat_style_delta: { ...delta(aboveDew), definition: 'reading temperature minus dew-point saturation temperature at the reading pressure', relation_to_dew: relation(aboveDew) },
        subcooling_style_delta: { ...delta(belowBubble), definition: 'bubble-point saturation temperature at the reading pressure minus reading temperature', relation_to_bubble: relation(-belowBubble) },
        lookup_resolution_k: rounded(resolution, 6), atmosphere: record, atmosphere_used: GAUGE.includes(pUnit),
        observation: 'Arithmetic comparison of one supplied reading with generated saturation data. It does not say whether the reading is normal, what causes it, or what to do.',
        not_determined: ['normal operating range', 'fault or cause', 'sensor accuracy or placement', 'whether the pressure and temperature were taken at the same point'] },
      [ev(`saturation table ${table.id}`, table.evidence), ...unitEvidence(['temperature_scales', 'psi_definition', ...keys])], [tableSource(table)],
      ['Superheat- and subcooling-style deltas are observations, never a diagnosis.', 'No normal range is applied: the only source range found (an internal application normal-ranges.ts) is UNVERIFIED.']];
    },
    exposure_limits(args) {
      fields(args, ['substance'], ['issuer', 'policy_set_points']);
      if (typeof args.substance !== 'string' || !SUBSTANCES.includes(pyStrip(args.substance).toLowerCase())) throw new ToolInputError('unknown_substance', 'Only ammonia (NH3, R717) limits are recorded in v0.1');
      const issuer = args.issuer ?? null;
      if (issuer !== null && !has(ISSUERS, issuer)) throw new ToolInputError('invalid_issuer', `issuer must be one of ${ISSUERS.join(', ')}`);
      const supplied = args.policy_set_points === undefined ? [] : args.policy_set_points;
      if (!Array.isArray(supplied) || supplied.length > 16) throw new ToolInputError('invalid_policy', 'policy_set_points must be a list of at most 16 entries');
      const policies = supplied.map(policy);
      const limits = limitsData.limits.filter(row => issuer === null || row.issuer === issuer).map(row => ({ id: row.id, value_kind: 'published_limit', issuer: row.issuer, kind: row.kind, label: row.label,
        concentration: { value: row.concentration.value, unit: 'ppm' }, mass_concentration: row.mass_concentration === null ? null : { value: row.mass_concentration.value, unit: 'mg/m3' },
        averaging: row.averaging, legal_status: row.legal_status, display: `${row.label}: ${fmt(row.concentration.value)} ppm`, evidence: row.evidence }));
      return ['exposure_limits_listed', { substance: limitsData.substance, published_limits: limits, policy_set_points: policies, gaps: limitsData.gaps, scope: limitsData.scope,
        separation: 'Published limits and policy set points are different kinds. A policy set point is never a legal or published limit.' },
      [...limits.map(row => ev(`published limit ${row.id}`, row.evidence)), ...policies.map(row => ev(`policy set point ${row.label}`, row.evidence))],
      [{ projection: 'exposure-limits.json', schema: 'exposure-limits/1', sha256: limitsSha }],
      ['Reference data for a person, not an exposure assessment, respirator selection or go/no-go call.', 'ERPG-1/2/3 are an explicit gap: no primary AIHA source was read.']];
    },
    resolve_equipment_kind(args) {
      fields(args, ['term'], ['vocabulary']);
      const vocabulary = args.vocabulary === undefined ? 'equipment_kind' : args.vocabulary;
      if (!has(['equipment_kind', 'line_service'], vocabulary)) throw new ToolInputError('invalid_vocabulary', 'vocabulary must be equipment_kind or line_service');
      const result = vocabulary === 'equipment_kind' ? resolveKind(args.term) : resolveService(args.term);
      if (vocabulary === 'line_service') result.open_decisions = plant.line_service_open_decisions.map(id => ({ id, topic: openDecisions[id].topic, status: 'DISPUTED', chosen: null }));
      const evidence = [ev(`${vocabulary} ${result.normalised}`, result.evidence)];
      if (vocabulary === 'line_service') evidence.push(...plant.line_service_open_decisions.map(id => ev(`open decision ${id}`, openDecisions[id].evidence)));
      const sources = [{ projection: 'plant-taxonomy.json', schema: 'plant-taxonomy/1', sha256: plantSha }];
      if (vocabulary === 'line_service') sources.push({ projection: 'open-decisions.json', schema: 'open-decisions/1', sha256: decisionsSha });
      return [`${vocabulary}${result.resolved ? '_resolved' : '_unresolved'}`, result, evidence, sources,
        ['Taxonomy and aliases are CHECK; no SME has reviewed the kind boundaries.', 'An unresolved term is reported as unresolved, never guessed.']];
    },
  };
  const fmt = ppm => Number.isInteger(ppm) ? String(ppm) : pyFloat(ppm);
  const policy = value => {
    const fail = message => new ToolInputError('invalid_policy', message);
    if (!isObject(value) || !keysAre(value, ['label', 'concentration', 'set_by', 'scope', 'reason'])) throw fail('A policy set point needs exactly label, concentration, set_by, scope, reason');
    let ppm;
    try { [ppm] = quantity(value.concentration, ['ppm'], 'concentration'); } catch (error) { if (error instanceof UnitError) throw fail(error.message); throw error; }
    const bounded = (text, name) => { if (typeof text !== 'string' || text.length > 2048) throw fail(`${name} must be bounded text`); };
    bounded(value.set_by, 'setBy');
    bounded(value.reason, 'reason');
    if (!has(POLICY_SCOPES, value.scope)) throw fail('Policy scope must be plant, client or expression');
    if (!pyStrip(value.set_by)) throw fail('A policy value needs the role that set it.');
    if (!pyStrip(value.reason)) throw fail('A policy value needs a reason.');
    if (ppm < 0) throw fail('Concentration cannot be negative');
    if (typeof value.label !== 'string' || !pyStrip(value.label) || value.label.length > 120) throw fail('A policy set point needs a short label');
    if (PUBLISHED_WORDS.test(value.label)) throw fail('A policy label must not name an issuer, a limit type or legal status');
    return { value_kind: 'policy_set_point', label: value.label, concentration: { value: ppm, unit: 'ppm' }, legal_status: 'not_a_legal_limit',
      display: `Policy set point (${value.scope}, set by ${value.set_by}), not a legal or published limit: ${value.label} ${fmt(ppm)} ppm`,
      evidence: { basis: { kind: 'policy', setBy: value.set_by, scope: value.scope, reason: value.reason }, status: 'CHECK' } };
  };
  const normalise = term => {
    if (typeof term !== 'string' || !pyStrip(term) || term.length > 128) throw new ToolInputError('invalid_term', 'A term must be short nonempty text');
    return pyStrip(term).toLowerCase().replace(/[\s_\x1c-\x1f\x85]+/g, '-');
  };
  const lineage = id => {
    const chain = [], seen = new Set();
    while (id !== null && !seen.has(id)) { seen.add(id); chain.push(id); id = kinds[id].parent; }
    return chain;
  };
  const resolveKind = term => {
    const key = normalise(term);
    if (!Object.hasOwn(plant.aliases, key)) return { vocabulary: 'equipment_kind', term, normalised: key, resolved: false, kind: null, evidence: plant.evidence, note: 'No alias matches. The term was not guessed into a kind.' };
    const id = plant.aliases[key], note = Object.hasOwn(plant.alias_notes, key) ? plant.alias_notes[key] : null;
    const evidence = note === null ? plant.evidence : { basis: { kind: 'practice', note: `${plant.evidence.basis.note} Alias note: ${note}` }, status: 'CHECK' };
    return { vocabulary: 'equipment_kind', term, normalised: key, resolved: true, kind: { id, label: kinds[id].label, lineage: lineage(id) }, alias_is_canonical_id: key === id,
      legacy_sources: plant.legacy_lists.filter(entry => entry.values.some(v => normalise(v) === key)).map(entry => entry.id), evidence, note };
  };
  const resolveService = term => {
    if (typeof term !== 'string' || !pyStrip(term) || term.length > 16) throw new ToolInputError('invalid_term', 'A line-service code must be short text');
    const code = pyStrip(term).toUpperCase();
    if (!Object.hasOwn(services, code) || code === '?') return { vocabulary: 'line_service', term, normalised: code, resolved: false, service: null, evidence: plant.evidence, note: 'Not a registered line-service code. The term was not guessed into a service.' };
    const { evidence, ...service } = services[code];
    return { vocabulary: 'line_service', term, normalised: code, resolved: true, service, evidence, note: `Pressure class and marker colours depend on open SME decisions: ${plant.line_service_open_decisions.join(', ')}.` };
  };

  const run = (name, argumentsText) => {
    if (!TOOLS.includes(name)) throw new KernelRefusal('unknown_tool', `No kernel tool ${name}`);
    const { value, inputSha256 } = parseArguments(argumentsText);
    const base = { schema: RECEIPT_SCHEMA, foundation_version: VERSION, tool: name, input_sha256: inputSha256, boundary: { ...BOUNDARY } };
    try {
      const [assessment, result, evidence, sources, limitations] = tools[name](value);
      return { ...base, status: 'success', assessment, result, error: null, evidence, data_sources: sources, limitations: [...COMMON_LIMITATIONS, ...limitations] };
    } catch (error) {
      if (error instanceof ToolInputError) return { ...base, status: 'error', assessment: 'tool_error', result: null, error: { code: error.code, message: error.message }, evidence: [], data_sources: [], limitations: [...COMMON_LIMITATIONS] };
      if (error instanceof UnitError) return { ...base, status: 'error', assessment: 'tool_error', result: null, error: { code: 'invalid_quantity', message: error.message }, evidence: [], data_sources: [], limitations: [...COMMON_LIMITATIONS] };
      throw error;
    }
  };
  return { foundation: 'foundation_refrigeration', version: VERSION, tools: TOOLS, run, projections: data };
}
