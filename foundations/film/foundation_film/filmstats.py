import argparse
from decimal import Decimal, ROUND_HALF_UP
import json
import math

from .cinema import shots


def milli(value):
    return int((Decimal(str(value)) * 1000).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def cam(a, b):
    import cv2
    import numpy as np

    ga, gb = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    p = cv2.goodFeaturesToTrack(ga, 400, 0.01, 8)
    if p is None or len(p) < 12:
        return None
    q, st, _ = cv2.calcOpticalFlowPyrLK(ga, gb, p, None)
    if q is None or st is None:
        return None
    p, q = p[st == 1], q[st == 1]
    if len(p) < 12:
        return None
    matrix, inliers = cv2.estimateAffinePartial2D(p, q, ransacReprojThreshold=2.0)
    if matrix is None:
        return None
    scale = float(np.hypot(matrix[0, 0], matrix[1, 0]))
    roll = float(np.degrees(np.arctan2(matrix[1, 0], matrix[0, 0])))
    predicted = (p @ matrix[:, :2].T) + matrix[:, 2]
    residual = float(np.median(np.linalg.norm(q - predicted, axis=1)))
    return dict(tx=float(matrix[0, 2]), ty=float(matrix[1, 2]), zoom=scale - 1,
                roll=roll, resid=residual, inl=float(inliers.mean()))


def still(frame):
    import cv2
    import numpy as np

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    height, width = gray.shape
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    cells = [lap[r * height // 3:(r + 1) * height // 3,
                 c * width // 3:(c + 1) * width // 3].var() for r in range(3) for c in range(3)]
    y = gray.astype(float)
    bright, dark = y > np.percentile(y, 80), y < np.percentile(y, 20)
    blue, red = frame[..., 0].astype(float), frame[..., 2].astype(float)
    warm = lambda mask: float((red[mask].mean() - blue[mask].mean()) / 255) if mask.any() else 0.0
    corner = np.concatenate([y[:height // 6, :width // 6].ravel(), y[:height // 6, -width // 6:].ravel(),
                             y[-height // 6:, :width // 6].ravel(), y[-height // 6:, -width // 6:].ravel()])
    centre = y[height // 3:2 * height // 3, width // 3:2 * width // 3]
    return dict(sharp=float(lap.var()), dof=float(np.log10((max(cells) + 1) / (min(cells) + 1))),
                luma=float(y.mean() / 255), p5=float(np.percentile(y, 5) / 255),
                p95=float(np.percentile(y, 95) / 255), black=float((y < 16).mean()),
                sat=float(hsv[..., 1].mean() / 255), warm_hi=warm(bright), warm_lo=warm(dark),
                vignette=float(corner.mean() / (centre.mean() + 1)),
                edges=float((cv2.Canny(gray, 80, 160) > 0).mean()))


def measure_shot(frames, start, end, fps):
    import numpy as np

    if not frames or not math.isfinite(fps) or fps <= 0:
        raise ValueError("a shot needs frames and a positive finite sampling rate")
    motion = [m for m in (cam(a, b) for a, b in zip(frames, frames[1:])) if m]
    stats = [still(frame) for frame in frames[::max(1, len(frames) // 6)]]
    speed = lambda key, scale=1: round(float(np.median([abs(m[key]) for m in motion])) * fps * scale, 3) if motion else 0.0
    pan, tilt, zoom = speed("tx"), speed("ty"), speed("zoom", 100)
    kind = ("static" if max(pan, tilt) < 4 and zoom < 1 else
            "push/pull" if zoom >= 1 and zoom * 6 > max(pan, tilt) / 10 else "pan" if pan >= tilt else "tilt")
    metrics = {key: milli(round(float(np.mean([s[key] for s in stats])), 4)) for key in stats[0]}
    metrics.update(subject_motion=milli(speed("resid")), pan_px_s=milli(pan), tilt_px_s=milli(tilt),
                   zoom_pct_s=milli(zoom), roll_deg_s=milli(speed("roll")),
                   jitter=milli(round(float(np.std([m["tx"] for m in motion])) * fps, 3) if len(motion) > 2 else 0))
    result = dict(start_ms=milli(start), end_ms=milli(end), camera=kind, metrics=metrics)
    shots([result])
    return result


def measure_video(source, fps=8.0, width=640):
    import cv2
    from scenedetect import SceneManager, open_video
    from scenedetect.detectors import AdaptiveDetector, ContentDetector

    if not math.isfinite(fps) or fps <= 0 or type(width) is not int or width < 6:
        raise ValueError("fps must be positive and finite; width must be an integer >= 6")
    video = open_video(str(source))
    native, duration = video.frame_rate, video.duration.get_seconds()
    manager = SceneManager()
    manager.add_detector(AdaptiveDetector(min_scene_len=6))
    manager.add_detector(ContentDetector(threshold=30, min_scene_len=6))
    manager.detect_scenes(video, show_progress=False)
    cuts = sorted({round(a.get_seconds(), 3) for a, _ in manager.get_scene_list()} | {0.0})
    cap, frames = cv2.VideoCapture(str(source)), []
    step, index = max(1, round(native / fps)), 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if index % step == 0:
                height = max(6, int(frame.shape[0] * width / frame.shape[1]))
                frames.append((index / native, cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)))
            index += 1
    finally:
        cap.release()
    if not frames or index / native + 1 / native < duration:
        raise ValueError("video could not be decoded completely")
    result = [measure_shot([frame for t, frame in frames if a <= t < b], a, b, native / step)
              for a, b in zip(cuts, cuts[1:] + [duration])]
    shots(result)
    return {"shots": result}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("--fps", type=float, default=8.0)
    parser.add_argument("--width", type=int, default=640)
    args = parser.parse_args()
    print(json.dumps(measure_video(args.video, args.fps, args.width), allow_nan=False))


if __name__ == "__main__":
    main()
