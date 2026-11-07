"""Controller side of one EndoForge run. Python holds the decision, the grant and both ledgers; the cohort stays in V8."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile

from extensions.cstack_forge import FORGE_CAPABILITY
from poodo_core import ContractError, canonical, outcome_for
from poodo_core.models import Document

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor/endoforge"
SUPERVISOR = ROOT / "adapters/workcell/supervisor.mjs"
EVALUATOR_ROOT = ROOT / "adapters/workcell"
PINS = ROOT / "contracts/SOURCE-PINS.json"
MAX_FRAME = 8 * 1024 * 1024
INVARIANTS = ["declared_imports", "foundation_pins"]
RESULT_LIMITS = {"wallMs": 30000, "memoryBytes": 16777216, "fuel": 4096}
ALLOWED_DECISION_EFFECT = "decision:accepted"


def _ledger_module():
    if str(VENDOR) not in sys.path:
        sys.path.insert(0, str(VENDOR))
    from core.ledger.frozen import FrozenEvaluators
    from core.ledger.ledger import Ledger
    return Ledger, FrozenEvaluators


class SupervisorLost(RuntimeError):
    pass


class NotExecuted(RuntimeError):
    """Nothing ran: the run stopped before any candidate was released to a cell."""


def verify_runtime():
    """Check the JS that judges and the vendored engine against their pins, before anything starts. Returns their identity."""
    pins = json.loads(PINS.read_text())
    pinned = pins.get("workcell_runtime", {}).get("files")
    if not pinned:
        raise NotExecuted("the workcell runtime has no pin")
    actual = {p.relative_to(EVALUATOR_ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in EVALUATOR_ROOT.rglob("*") if p.is_file()}
    changed = sorted(name for name in pinned.keys() | actual.keys() if pinned.get(name) != actual.get(name))
    if changed:
        raise NotExecuted("the workcell runtime differs from its pin: " + ", ".join(changed)[:200])
    raw = (VENDOR / "SOURCE-MANIFEST.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != pins["endoforge"]["source_manifest_sha256"]:
        raise NotExecuted("the vendored EndoForge manifest differs from its pin")
    for name, expected in json.loads(raw)["files"].items():
        if hashlib.sha256((VENDOR / name).read_bytes()).hexdigest() != expected:
            raise NotExecuted("the vendored EndoForge differs from its pin: " + name)
    return hashlib.sha256(canonical({"workcell": pinned, "endoforge": pins["endoforge"]["source_manifest_sha256"]}).encode("ascii")).hexdigest()


class Supervisor:
    """One node supervisor outside every cohort. Losing it loses attempts, never the task."""
    def __init__(self, config, on_call):
        self._on_call = on_call
        self._next = 0
        argument = json.dumps({key: config[key] for key in ("size", "isolation", "foundations", "transport", "jobTimeoutMs", "cgroupRoot")
                               if config.get(key) is not None})
        self._stderr = tempfile.TemporaryFile()
        try:
            self.process = subprocess.Popen(["node", str(SUPERVISOR), argument], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            stderr=self._stderr, start_new_session=True, cwd=ROOT)
        except OSError as error:
            self._stderr.close()
            raise NotExecuted("node could not start; install Node 22 or newer and put it on PATH") from error

    def ask(self, op, payload=None):
        self._next += 1
        ident = self._next
        self._write({"id": ident, "op": op, "input": payload})
        while True:
            line = self.process.stdout.readline(MAX_FRAME + 1)
            if not line.endswith(b"\n"):
                raise SupervisorLost("supervisor closed its channel: " + self.diagnostics())
            message = json.loads(line)
            if "call" in message:
                self._answer(message)
            elif message.get("id") == ident:
                return message

    def diagnostics(self):
        self._stderr.seek(0, os.SEEK_END)
        self._stderr.seek(max(0, self._stderr.tell() - 400))
        return self._stderr.read().decode("utf-8", "replace").strip()[-300:]

    def _answer(self, message):
        try:
            reply = {"reply": message["call"], "result": self._on_call(message["request"], message["context"])}
        except Exception as error:
            reply = {"reply": message["call"], "error": str(error) or "host call failed"}
        self._write(reply)

    def _write(self, message):
        try:
            self.process.stdin.write(json.dumps(message).encode("ascii") + b"\n")
            self.process.stdin.flush()
        except OSError as error:
            raise SupervisorLost("supervisor closed its channel") from error

    def close(self):
        try:
            self._write({"op": "close"})
            self.process.wait(timeout=5)
        except (SupervisorLost, subprocess.TimeoutExpired):
            pass
        finally:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except OSError:
                pass
            self.process.wait()
            for stream in (self.process.stdin, self.process.stdout):
                try:
                    stream.close()
                except OSError:
                    pass
            self._stderr.close()


class WorkcellCapability:
    """Runs a goal in IsolatePool workcells. Bound once by bootstrap; request data cannot select any of this."""
    def __init__(self, source_root=None):
        self._host = None

    def bind(self, *, grant_id, config, endoforge, session_id, propose):
        self._host = dict(grant_id=grant_id, config=config, endoforge=endoforge, session_id=session_id, propose=propose)

    def describe(self):
        return FORGE_CAPABILITY

    def invoke(self, request, attempt_id, cancellation=None):
        if self._host is None:
            return outcome_for(request, attempt_id, "unavailable", "workcell_not_configured",
                               limitations=("This host has no workcell configuration.",))
        run = _Run(self._host, request, attempt_id)
        try:
            report = run.execute()
        except NotExecuted as error:
            report = dict(status="unavailable", reason=str(error), candidates=[])
        except Exception as error:
            report = run.lost(str(error) or type(error).__name__)
        return run.outcome(report)


class _Run:
    def __init__(self, host, request, attempt_id):
        self.host, self.request, self.attempt_id = host, request, attempt_id
        self.arguments = Document.capture(request.arguments).read()
        self.proposals = []
        self.identity = None
        self.receipts = []
        self.in_flight = False
        self.runtime_pin = None

    @property
    def granted(self):
        declared = self.arguments["declared_imports"]
        return [name for name in declared if name in self.host["config"]["foundation_imports"]]

    def execute(self):
        declared = self.arguments["declared_imports"]
        undeclared = [name for name in declared if name not in self.host["config"]["foundation_imports"]]
        if undeclared:
            return dict(status="refused", reason="declared_import_not_granted", refused=undeclared, candidates=[])
        self.runtime_pin = verify_runtime()
        Ledger, Frozen = _ledger_module()
        self.ledger = Ledger(self.host["config"]["ledger"])
        self.frozen = self._freeze(Ledger, Frozen)
        supervisor = Supervisor({**self.host["config"], "foundations": self.granted}, self._on_call)
        try:
            return self._rounds(supervisor)
        finally:
            supervisor.close()

    def _unique(self, kind):
        return f"{kind}:{self.host['session_id']}:{self.request.decision_id}:{self.attempt_id}"

    def _freeze(self, Ledger, Frozen):
        task, admitted = self._unique("task"), self._unique("input")
        args = self.arguments
        self.ledger.append(dict(version=0, kind="task", id=task, data=dict(intent=args["need"], acceptance=canonical(args["checks"]))))
        self.ledger.append(dict(version=0, kind="admitted_input", id=admitted,
                                data=dict(task=task, content=canonical({k: args[k] for k in ("need", "signature", "cases", "declared_imports")}),
                                          origin=f"decision {self.request.decision_id}")))
        gate_input = dict(version=1, contract=dict(version=1, signature=args["signature"], refusals=[], tolerance=0, sources=[f"grant {self.host['grant_id']}"]),
                          cases=args["cases"], limits=RESULT_LIMITS,
                          allowedEffects=sorted(f"import:{name}" for name in self.granted) + [ALLOWED_DECISION_EFFECT])
        configuration = dict(gateInput=gate_input, invariants=INVARIANTS, objectives=dict(wasm_bytes="min"))
        record = Frozen(self.ledger).freeze(str(EVALUATOR_ROOT), task=task, admitted_input=admitted, confirmed_by=f"decision {self.request.decision_id}",
                                            qualification="host-authored checks judged by the pinned Foundation",
                                            synthesis_context=dict(id=self._unique("context"), candidate_blind="confirmed", inputs=[admitted]),
                                            configuration=configuration, residual=canonical({"checks": args["checks"]}), invariant_version="cstack-workcell/1")
        self.task, self.admitted = task, admitted
        return record

    def _prompt(self, diagnostics):
        args = self.arguments
        return {"need": args["need"], "signature": args["signature"], "declared_imports": self.granted, "cases": args["cases"], "diagnostics": diagnostics}

    def _rounds(self, supervisor):
        ready = supervisor.ask("ready")
        if "error" in ready:
            raise NotExecuted("the workcell did not start: " + str(ready["error"])[:300])
        self.compiler = ready["result"]["compiler"]
        diagnostics, candidates = [], []
        for number in range(self.arguments["max_candidates"]):
            generated = supervisor.ask("generate", self._prompt(diagnostics))
            if "error" in generated:
                reason = "model transport: " + str(generated["error"])[:200]
                return dict(status="rejected", reason=reason, candidates=candidates) if candidates else dict(status="model_unavailable", reason=reason, candidates=[])
            text, model = generated["result"]["text"], generated["result"]["model"]
            result = self._attempt(supervisor, number, text, model)
            if result["status"] == "unavailable":
                raise NotExecuted(result["reason"])
            candidates.append(result)
            if result["status"] != "rejected" or result["refused"]:
                return dict(status="refused" if result["refused"] else result["status"], reason=result["reason"], candidates=candidates)
            diagnostics = result["diagnostics"]
        return dict(status="rejected", reason="no candidate passed within max_candidates", candidates=candidates)

    def _attempt(self, supervisor, number, text, model):
        candidate = "cand:" + hashlib.sha256(f"{self.task}\n{text}".encode("utf-8")).hexdigest()
        provenance = dict(origin="generated", upstream_identity="model transport", upstream_version=str(model["version"]),
                          input_scopes=[], derived_from=[self.admitted], model=dict(identity=str(model["identity"]), version=str(model["version"])))
        license_record = dict(expression="GPL-3.0-only", evidence_sha256=hashlib.sha256((ROOT / "LICENSE").read_bytes()).hexdigest())
        existing = {r["id"] for r in self.ledger.records()}
        if candidate not in existing:
            self.ledger.append(dict(version=1, kind="candidate", id=candidate, provenance=provenance, license=license_record,
                                    data=dict(task=self.task, admitted_input=self.admitted, content=text, proposer=str(model["identity"]))))
        environment = dict(decision_id=self.request.decision_id, grant_id=self.host["grant_id"], request_sha256=self.request.sha256,
                           attempt_id=self.attempt_id, session_id=self.host["session_id"], runtime_pin_sha256=self.runtime_pin, compiler=self.compiler, foundation_imports=self.granted)
        receipt = dict(version=1, kind="receipt", id=f"{self._unique('receipt')}:{number}", provenance=provenance | dict(derived_from=[candidate]), license=license_record, data=dict(
            task=self.task, candidate=candidate, frozen_evaluator=self.frozen["id"],
            precommit=dict(observable="the candidate kernel's outputs and effects", acceptance_boundary="all gates and held-out Foundation checks pass",
                           oracle=self.frozen["id"], oracle_version=self.frozen["data"]["freeze"]["digest"], artifact_identity=candidate,
                           environment=environment, failure_meaning="the candidate is not accepted",
                           stop_condition="one batch report, or outcome_unknown on a lost workcell"),
            delivery_state="running", outcome_state="unobserved", observations=[]))
        reference = dict(ledger=self.host["config"]["ledger"], identity=self.frozen["id"], root=str(EVALUATOR_ROOT))
        job = dict(reference=reference, candidates=[candidate], receipts=[receipt],
                   portOptions=dict(task=self.task, sources={candidate: text}, granted=self.granted, signature=self.arguments["signature"]))
        self.in_flight = True
        answer = supervisor.ask("run", job)
        self.in_flight = False
        return self._read_result(answer, candidate)

    def _read_result(self, answer, candidate):
        result = answer.get("result") or {}
        if "error" in answer and not result:
            return dict(status="unavailable", reason="the pool refused the job before dispatch: " + str(answer["error"])[:300], candidate=candidate, refused=False, diagnostics=[])
        evidence = result.get("evidence") or {}
        self.identity = evidence or self.identity
        receipts = [dict(id=r["record"]["id"], hash=r["hash"], delivery_state=r["record"]["data"]["delivery_state"],
                         outcome_state=r["record"]["data"]["outcome_state"]) for r in result.get("receipts", [])]
        self.receipts.extend(receipts)
        states = {r["outcome_state"] for r in receipts}
        attempts = (result.get("report") or {}).get("attempts", [])
        failures = [dict(stage=a["stage"], first_failure=a["firstFailure"], results=[r for r in a["results"] if not r["passed"]]) for a in attempts if a["stage"] != "passed"]
        refused = any(p.get("accepted") is not True for p in evidence.get("proposals", []))
        if result.get("status") == "outcome_unknown" or "inconclusive" in states or not states:
            status = "outcome_unknown"
        elif states == {"passed"} and not refused:
            status = "passed"
        else:
            status = "rejected"
        diagnostics = [dict(check=f["first_failure"], reasons=[r["reason"] for r in f["results"]]) for f in failures]
        compile_notes = evidence.get("diagnostics", {}).get(candidate)
        if compile_notes:
            diagnostics.append(dict(check="compile", reasons=[compile_notes]))
        return dict(status=status, reason=result.get("reason") or (failures[0]["first_failure"] if failures else None), candidate=candidate, refused=refused,
                    diagnostics=diagnostics, isolation=result.get("isolation"), workcell=result.get("workcell"), cgroup=result.get("cgroup"),
                    wasm=evidence.get("artifacts", {}).get(candidate), attributions=evidence.get("broker", {}).get("attributions", []),
                    attributions_omitted=evidence.get("broker", {}).get("attributions_omitted", 0),
                    calls=evidence.get("broker", {}).get("calls", 0), foundation_ns=evidence.get("broker", {}).get("foundation_ns"),
                    window_ns=evidence.get("window_ns"), runs=evidence.get("runs", []), broker_refusals=evidence.get("broker", {}).get("refusals", []),
                    proposals=evidence.get("proposals", []), receipts=receipts)

    def _on_call(self, request, context):
        if type(request) is not dict or request.get("kind") != "propose_decision" or set(request) != {"kind", "candidate", "proposal"}:
            raise ContractError("Unknown host call")
        answer = self.host["propose"](self, request["proposal"])
        self.proposals.append(dict(answer, candidate=request["candidate"]))
        return answer

    def lost(self, reason):
        return dict(status="outcome_unknown" if self.in_flight else "unavailable", reason=reason, candidates=[])

    def outcome(self, report):
        identity = self.identity or {}
        receipt = dict(schema="cstack.forge-receipt/0.1", status=report["status"], reason=report.get("reason"),
                       decision_id=self.request.decision_id, grant_id=self.host["grant_id"], request_sha256=self.request.sha256,
                       attempt_id=self.attempt_id, session_id=self.host["session_id"], runtime_pin_sha256=self.runtime_pin,
                       task=getattr(self, "task", None), frozen_evaluator=(getattr(self, "frozen", None) or {}).get("id"),
                       oracle_digest=(getattr(self, "frozen", None) or {"data": {"freeze": {"digest": None}}})["data"]["freeze"]["digest"],
                       compiler=identity.get("compiler") or getattr(self, "compiler", None), foundations=identity.get("foundations", {}),
                       candidates=report.get("candidates", []), receipts=self.receipts, proposals=self.proposals)
        status = report["status"]
        if status in ("unavailable", "model_unavailable"):
            assessment = "workcell_not_executed" if status == "unavailable" else "candidate_model_unavailable"
            return outcome_for(self.request, self.attempt_id, "unavailable", assessment,
                               limitations=("No candidate was released to a cell.", "Reason: " + str(report.get("reason"))[:300]))
        if status == "passed":
            return outcome_for(self.request, self.attempt_id, "completed", "candidate_passed", certainty="responded", raw_result=receipt,
                               scope="One candidate against one frozen evaluator.", limitations=("Passing is not goal acceptance.",))
        if status == "outcome_unknown":
            return outcome_for(self.request, self.attempt_id, "indeterminate", "outcome_unknown", certainty="unknown",
                               limitations=("No automatic retry; the attempt may have executed.", "Reason: " + str(report.get("reason"))[:200],
                                            "Receipts: " + canonical(self.receipts)[:1000]))
        return outcome_for(self.request, self.attempt_id, "tool_error", "candidate_" + status, certainty="responded", raw_result=receipt,
                           scope="One candidate against one frozen evaluator.", limitations=("A refused or rejected run records no pass.",))
