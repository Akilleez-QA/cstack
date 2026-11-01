"""Foundation Film as a sibling POODO extension: pins, round trips and fail-closed controls on the shared bridge."""
import ast
import copy
import json
from pathlib import Path
import tempfile
import unittest

from adapters.execution import ProcessResult
from adapters.foundation_stdio import arguments_sha256
from adapters.memory_ledger import MemoryLedger
from adapters.wire import encode
from bootstrap import DEFAULT_FILM_ROOT, DOMAINS
from extensions.foundation_math import FoundationMath
from poodo_core import AuthorityGrant, ContractError, Phase, PhaseCheckpoint, PoodoCore
from tests.helpers import precommit, request, to_decide

ROOT = Path(__file__).resolve().parents[1]
# A checkout without foundations/film (the open-core export) skips every test here.
HAVE_FILM = DEFAULT_FILM_ROOT.is_dir()
if HAVE_FILM:
    from adapters.film_stdio import (BRIDGE_PROTOCOL, INVENTORY_SHA256, SOURCE_FILE_COUNT, SOURCE_SHA256,
                                     FilmStdioCapability, PinnedFilmSource)
    from extensions.foundation_film import FILM_DOMAIN_ID, FILM_TOOL_NAMES, FoundationFilm

SHOTS = [{"start_ms": 0, "end_ms": 6000, "camera": "pan",
          "metrics": {"sharp": 220000, "black": 40, "subject_motion": 1900, "luma": 330}},
         {"start_ms": 6000, "end_ms": 9000, "camera": "static",
          "metrics": {"sharp": 700000, "black": 720, "subject_motion": 100, "luma": 90}}]
BANDS = {"moving_share": 508, "metrics": {"sharp": [130039, 223214, 338637], "black": [30, 47, 184],
                                         "subject_motion": [800, 1833, 10604], "luma": [158, 329, 584]}}
CASES = {
    "cinematic_gate": ({"shots": SHOTS, "bands": BANDS, "segments": [{"id": "b1", "start_ms": 0, "end_ms": 6000},
                                                                    {"id": "b2", "start_ms": 6000, "end_ms": 9000}]},
                       "thresholds_not_met"),
    "reference_bands": ({"shots": SHOTS}, "bands_measured"),
    "audio_gate": ({"integrated_lufs": -16200, "true_peak_dbtp": -1500, "voice_over_bed_db": 13500, "cuts": 10,
                    "cuts_with_hit": 9, "heard": ["Speech", "Music"], "line_wer": [{"line": "b1-1", "wer_permille": 20}]},
                   "thresholds_met"),
    "drift_verdict": ({"frames": {"edge_f1": [980, 700, 80], "mask_iou": [840, 700, 0]}}, "thresholds_not_met"),
    "cue_vocabulary_check": ({"provided": [{"id": "b4:w:heat", "t_ms": 41000}], "aliases": {"b4:heat": "b4:w:heat"},
                              "lanes": [{"lane": "scene-b04", "references": ["b4:heat", "slam-1"]}]},
                             "thresholds_not_met"),
    "look_gate": ({"frames": [{"id": "b4-k00", "metrics": {
        "palette_ab": 2000, "palette_L": 3000, "median_L": 1000, "range_L": 4000, "clip_white": 0, "clip_black": 0,
        "detail_ratio": 990, "chroma_ratio": 1050}}]}, "thresholds_met"),
}


def film_request(name="drift_verdict", args=None, i=1, **kw):
    return request(name, CASES[name][0] if args is None else args, FILM_DOMAIN_ID, i=i, **kw)


def core():
    grant = AuthorityGrant("test-film", FILM_DOMAIN_ID, FILM_DOMAIN_ID, FILM_TOOL_NAMES, ("g",), 16, lane="ToolFace")
    return FoundationFilm(FilmStdioCapability(DEFAULT_FILM_ROOT), (grant,), MemoryLedger())


class FakeExecutor:
    def __init__(self, result=None, mutation=None):
        self.result, self.mutation, self.calls = result, mutation, 0

    def exchange(self, frames, cancellation=None):
        self.calls += 1
        hello = {"jsonrpc": "2.0", "id": "cstack-init", "result": {"protocolVersion": BRIDGE_PROTOCOL,
                 "mcpCompatible": False, "limits": {"inputFrameBytes": 65_536, "outputFrameBytes": 1_048_576}}}
        reply = {"jsonrpc": "2.0", "id": json.loads(frames[1])["id"], "result": copy.deepcopy(self.result)}
        if self.mutation:
            self.mutation(reply)
        return ProcessResult("completed", "responded", encode(hello) + b"\n" + encode(reply) + b"\n", b"", 0)


@unittest.skipUnless(HAVE_FILM, "Foundation Film is not in this checkout (foundations/film is absent)")
class FilmAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cap = FilmStdioCapability(DEFAULT_FILM_ROOT)
        cls.ok = cls.cap.invoke(film_request(), "attempt-control").to_dict()["raw_result"]

    def test_pins_match_the_foundation_contracts_and_registry(self):
        self.assertEqual(PinnedFilmSource(DEFAULT_FILM_ROOT).verify(),
                         {"source_manifest_sha256": SOURCE_SHA256, "verified_files": SOURCE_FILE_COUNT})
        pins_path = ROOT / "contracts/SOURCE-PINS.json"  # private record; the open-core export leaves it out
        if pins_path.is_file():
            pins = json.loads(pins_path.read_text())["foundation_film"]
            self.assertEqual((pins["source_manifest_sha256"], pins["source_manifest_entry_count"],
                              pins["inventory_sha256"]), (SOURCE_SHA256, SOURCE_FILE_COUNT, INVENTORY_SHA256))
        self.assertEqual(tuple(t["name"] for t in self.cap.inventory()), FILM_TOOL_NAMES)
        self.assertEqual(DOMAINS[FILM_DOMAIN_ID].tool_names, FILM_TOOL_NAMES)

    def test_every_tool_round_trips_over_the_real_bridge_with_evidence(self):
        for i, (name, (arguments, assessment)) in enumerate(CASES.items()):
            out = self.cap.invoke(film_request(name, i=i + 2), f"attempt-{name}").to_dict()
            receipt = out["raw_result"]["structuredContent"]["receipt"]
            self.assertEqual((out["execution_status"], out["assessment"]), ("completed", assessment), name)
            self.assertEqual(receipt["input_sha256"], arguments_sha256(arguments))
            self.assertTrue(receipt["evidence"])
            self.assertFalse(receipt["boundary"]["acceptance_decision"])

    def test_real_round_trip_through_the_inherited_core(self):
        foundation = core()
        to_decide(foundation, domain=FILM_DOMAIN_ID)
        req = film_request()
        foundation.decide(req, precommit())
        foundation.advance("g", Phase.ORCHESTRATE, PhaseCheckpoint("go", "Precommitted fixture"))
        out = foundation.execute(req.decision_id).to_dict()
        receipt = out["raw_result"]["structuredContent"]["receipt"]
        self.assertEqual((out["execution_status"], out["assessment"]), ("completed", "thresholds_not_met"))
        self.assertEqual(receipt["result"]["first_failing_frame"], 2)
        self.assertFalse(out["formal_proof"] or out["runtime_goal_acceptance"] or foundation.snapshot("g").closed)

    def test_bad_arguments_are_a_retained_tool_error(self):
        out = self.cap.invoke(film_request(args={"frames": {"edge_f1": [900], "depth_error": [5]}}),
                              "attempt-bad").to_dict()
        self.assertEqual((out["execution_status"], out["assessment"]), ("tool_error", "tool_error"))
        self.assertTrue(out["raw_result"]["structuredContent"]["receipt"]["evidence"])

    def test_dishonest_replies_quarantine(self):
        receipt = lambda x: x["result"]["structuredContent"]["receipt"]  # noqa: E731
        for mutate in (lambda x: receipt(x)["boundary"].update(acceptance_decision=True),
                       lambda x: receipt(x).update(input_sha256="0" * 64),
                       lambda x: receipt(x).update(evidence=[]),
                       lambda x: receipt(x)["result"].update(verdict="accepted"),
                       lambda x: receipt(x)["result"].update(first_failing_frame=-1),
                       lambda x: x["result"]["structuredContent"].update(assessment="film_accepted"),
                       lambda x: x["result"]["structuredContent"].update(runtime_goal_acceptance=True)):
            cap = FilmStdioCapability(DEFAULT_FILM_ROOT, executor=FakeExecutor(self.ok, mutate))
            cap._ready = True
            out = cap.invoke(film_request(), "attempt-mutated").to_dict()
            self.assertEqual((out["execution_status"], out["raw_result"]), ("protocol_error", None))

    def test_out_of_profile_unknown_or_unpinned_requests_never_dispatch(self):
        fake = FakeExecutor(self.ok)
        cap = FilmStdioCapability(DEFAULT_FILM_ROOT, executor=fake)
        for req, status in ((film_request(args={"frames": {"edge_f1": [0.98]}}), "resource_rejected"),
                            (request("render_shot", {}, FILM_DOMAIN_ID), "unavailable"),
                            (film_request(required_evidence="formal_proof"), "unavailable")):
            out = cap.invoke(req, "attempt-denied").to_dict()
            self.assertEqual((out["execution_status"], out["execution_certainty"]), (status, "not_dispatched"))
        with tempfile.TemporaryDirectory() as td:
            out = FilmStdioCapability(Path(td), executor=fake).invoke(film_request(), "attempt-src").to_dict()
            self.assertEqual(out["assessment"], "source_identity_unavailable")
        self.assertEqual(fake.calls, 0)

    def test_sibling_not_subclass_and_cross_domain_binding_refused(self):
        self.assertTrue(issubclass(FoundationFilm, PoodoCore))
        self.assertFalse(issubclass(FoundationFilm, FoundationMath))
        for path in (ROOT / "extensions/foundation_film.py", ROOT / "adapters/film_stdio.py"):
            modules = {n.module for n in ast.walk(ast.parse(path.read_text())) if isinstance(n, ast.ImportFrom)}
            self.assertFalse({"extensions.foundation_math", "adapters.math_stdio", "extensions.foundation_refrigeration",
                              "adapters.refrigeration_stdio"} & modules, path)
        math_grant = AuthorityGrant("m", "foundation_math", "foundation_math", ("exact_scalar",), ("g",), 1, lane="ToolFace")
        with self.assertRaises(ContractError):
            FoundationFilm(self.cap, (math_grant,), MemoryLedger())


if __name__ == "__main__":
    unittest.main()
