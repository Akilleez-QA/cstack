import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from foundation_film.cinema import cinematic_gate, reference_bands
from foundation_film.filmstats import measure_shot, measure_video, milli

VISION = all(importlib.util.find_spec(name) is not None for name in ("numpy", "cv2", "scenedetect"))


class FilmstatsBoundaryTests(unittest.TestCase):
    def test_milli_rounding(self):
        self.assertEqual([milli(v) for v in (0.0005, -0.0005, 1.2345, 12.345)], [1, -1, 1235, 12345])
        for value in (float("nan"), float("inf")):
            with self.assertRaises((ValueError, ArithmeticError)):
                milli(value)

    def test_imports_without_optional_dependencies(self):
        result = subprocess.run([sys.executable, "-B", "-S", "-c",
                                 "import foundation_film.tools; import foundation_film.filmstats"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


@unittest.skipUnless(VISION, "optional producer requires numpy, opencv-python-headless and scenedetect")
class FilmstatsVisionTests(unittest.TestCase):
    def test_uniform_frame_metrics_feed_the_existing_gate(self):
        import numpy as np

        shot = measure_shot([np.full((36, 48, 3), 128, np.uint8)], 0, 2, 8)
        self.assertEqual((shot["start_ms"], shot["end_ms"], shot["camera"]), (0, 2000, "static"))
        self.assertEqual({k: shot["metrics"][k] for k in ("sharp", "black", "luma", "subject_motion")},
                         {"sharp": 0, "black": 0, "luma": 502, "subject_motion": 0})
        self.assertTrue(all(type(v) is int for v in shot["metrics"].values()))
        _, measured = reference_bands({"shots": [shot]})
        assessment, _ = cinematic_gate({"shots": [shot], "bands": measured["bands"]})
        self.assertEqual(assessment, "thresholds_met")

    def test_optical_flow_distinguishes_a_pan_from_a_still(self):
        import cv2
        import numpy as np

        rng = np.random.default_rng(42)
        frame = rng.integers(0, 256, (96, 128, 3), dtype=np.uint8)
        moved = cv2.warpAffine(frame, np.float32([[1, 0, 2], [0, 1, 0]]), (128, 96))
        pan = measure_shot([frame, moved], 0, 1, 8)
        static = measure_shot([frame, frame], 0, 1, 8)
        self.assertEqual((pan["camera"], static["camera"]), ("pan", "static"))
        self.assertAlmostEqual(pan["metrics"]["pan_px_s"] / 1000, 16, delta=1)
        self.assertLess(pan["metrics"]["subject_motion"], 1000)

    def test_video_detection_and_cli_emit_bridge_ready_shots(self):
        import cv2
        import json
        import numpy as np

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "cuts.avi"
            writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"MJPG"), 10, (96, 72))
            self.assertTrue(writer.isOpened())
            try:
                for index in range(60):
                    writer.write(np.full((72, 96, 3), 0 if index < 30 else 255, np.uint8))
            finally:
                writer.release()
            result = subprocess.run([sys.executable, "-B", "-m", "foundation_film.filmstats", str(source),
                                     "--width", "96"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            arguments = json.loads(result.stdout)
            self.assertEqual([(s["start_ms"], s["end_ms"]) for s in arguments["shots"]], [(0, 3000), (3000, 6000)])
            self.assertEqual(reference_bands(arguments)[1]["total_ms"], 6000)
            with self.assertRaises(OSError):
                measure_video(Path(directory) / "missing.avi")

    def test_invalid_sampling_and_empty_shots_fail(self):
        for fps, width in ((0, 640), (float("nan"), 640), (8, 5)):
            with self.assertRaises(ValueError):
                measure_video("unused.avi", fps, width)
        with self.assertRaises(ValueError):
            measure_shot([], 0, 1, 8)
