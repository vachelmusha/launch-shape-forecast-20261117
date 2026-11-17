"""Conditional launch-shape ensemble; Python standard library, offline and deterministic."""
import bisect
import datetime as dt
import json
import math
import os
from pathlib import Path
from statistics import median

LEVELS = (0.05, 0.25, 0.5, 0.75, 0.95)
NORMAL = (-1.644854, -0.674490, 0.0, 0.674490, 1.644854)


def timestamp(value):
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def log_count(value):
    return math.log(max(1.0, float(value or 0)))


def hourly(rows, start, field="from"):
    """Normalize minute or hourly observations without treating missing reads as zero."""
    groups = {}
    for row in rows:
        key = math.floor((timestamp(row[field]) - start) / 3600 + 1e-7)
        bucket = groups.setdefault(key, [[], []])
        if row.get("viewers") is not None:
            bucket[0].append(float(row["viewers"]))
        if row.get("channels") is not None:
            bucket[1].append(float(row["channels"]))
    return {k: (sum(v[0]) / len(v[0]), sum(v[1]) / len(v[1]) if v[1] else None)
            for k, v in groups.items() if v[0]}


def metadata(text):
    text = text.lower()
    early = "early-access-contaminated" in text
    local = any(s in text for s in ("midnight local", "rolling", "midnight, rolling"))
    global_time = any(s in text for s in ("simultaneous", "global unlock", "single time"))
    console = (any(s in text for s in ("ps4", "ps5", "switch", "xbox"))
               and "pc," not in text and ", pc" not in text and not text.startswith("pc "))
    return (local, global_time, console, early)


def descriptor(points):
    base = log_count(points[0][0])
    # The shape immediately before the checkpoint distinguishes an already-active
    # launch from one whose main streaming audience has yet to unlock the game.
    windows = [(-2, -1), (-5, -3), (-11, -6), (-23, -12), (-47, -24)]
    features = []
    for first, last in windows:
        vals = [log_count(points[k][0]) - base for k in range(first, last + 1) if k in points]
        features.append(median(vals) if vals else None)
    past = [v[0] for k, v in points.items() if -48 <= k <= 0]
    features.append(log_count(max(past)) - base if past else None)
    # Viewers per broadcaster is useful only when both launches have channel data.
    channel = points[0][1]
    features.append(base - log_count(channel) if channel and channel > 0 else None)
    features.append(base)
    return features


def analogues(case):
    examples = []
    for comp in case.get("comparables", []):
        # The GTA VI category's premiere history is context, not a release-day sample.
        if "not a launch" in comp.get("unlock", "").lower():
            continue
        pts = hourly(comp["hourly"], timestamp(comp["day_start"]))
        if 0 not in pts or pts[0][0] < 5 or sum(h in pts for h in range(1, 24)) < 20:
            continue
        examples.append({"name": comp["name"], "points": pts,
                         "features": descriptor(pts),
                         "meta": metadata(comp.get("platforms", "") + " " + comp.get("unlock", ""))})
    return examples


def distance(a, b):
    # Clipped distances prevent an isolated missing prelaunch audience from
    # overpowering the checkpoint's better measured recent trajectory.
    weights = (1.4, 1.1, 0.8, 0.35, 0.2, 0.5, 0.15, 0.04)
    total = norm = 0.0
    for x, y, w in zip(a, b, weights):
        if x is not None and y is not None:
            total += w * min(9.0, (x - y) ** 2)
            norm += w
    return total / max(norm, 1e-9)


def scenario_weights(target, examples, bandwidth=0.65, meta_strength=1.0):
    a = target["meta"]
    weighted = []
    for ex in examples:
        b = ex["meta"]
        mismatch = (0.8 * (a[2] != b[2]) + 1.1 * (a[0] and b[1] and not b[0])
                    + 0.7 * (a[3] != b[3]))
        cost = distance(target["features"], ex["features"]) / bandwidth
        weighted.append((ex, math.exp(-min(60.0, cost + meta_strength * mismatch))))
    mass = sum(w for _, w in weighted)
    # A small population component protects against a misleadingly close match.
    return [(ex, 0.94 * w / max(mass, 1e-30) + 0.06 / len(examples)) for ex, w in weighted]


def weighted_quantile(samples, probability):
    samples = sorted(samples)
    total = sum(w for _, w in samples)
    centers, values = [], []
    running = 0.0
    for value, weight in samples:
        centers.append((running + weight / 2) / total)
        values.append(value)
        running += weight
    pos = bisect.bisect_left(centers, probability)
    if pos == 0:
        return values[0]
    if pos == len(centers):
        return values[-1]
    frac = (probability - centers[pos - 1]) / (centers[pos] - centers[pos - 1])
    return values[pos - 1] * (1 - frac) + values[pos] * frac


def predict(target, examples, bandwidth=0.65, meta_strength=2.0, spread=0.30):
    weighted = scenario_weights(target, examples, bandwidth, meta_strength)
    base = log_count(target["points"][0][0])
    out = []
    for h in range(1, 24):
        samples = []
        for ex, weight in weighted:
            pts = ex["points"]
            if h not in pts:
                continue
            ratio = log_count(pts[h][0]) - log_count(pts[0][0])
            # Spread each historical scenario into a small continuous mixture;
            # tail uncertainty increases with the forecast horizon.
            noise = spread * (0.6 + 0.4 * math.sqrt(h / 23))
            for z, mass in zip(NORMAL, (0.125, 0.25, 0.25, 0.25, 0.125)):
                samples.append((base + ratio + noise * z, weight * mass))
        q = [round(min(1e9, max(0.001, math.exp(weighted_quantile(samples, p)))), 4)
             for p in LEVELS]
        out.append({"hour": h + 1, "q": q})
    return {"hours": out}


def forecast(case):
    start = timestamp(case["day_start"])
    rows = case.get("history_hourly") or []
    points = hourly(rows, start) if rows else hourly(case.get("history", []), start, "at")
    known = next(r for r in case["known"] if r["hour"] == 1)
    points[0] = (max(1, known["viewers"]), known.get("channels"))
    target_meta = metadata(case.get("notes", "")[:550])
    if case.get("game", {}).get("name") == "Grand Theft Auto VI":
        # The final's published rules specify console-only, rolling local unlocks.
        target_meta = (True, False, True, False)
    target = {"points": points, "features": descriptor(points), "meta": target_meta}
    examples = analogues(case)
    if not examples:
        p = max(1, known["viewers"])
        return {"hours": [{"hour": h, "q": [round(min(1e9, p * math.exp(z * .15 * math.sqrt(h - 1))), 4)
                                               for z in NORMAL]} for h in range(2, 25)]}
    return predict(target, examples)


def main():
    source = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
    output = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    output.mkdir(parents=True, exist_ok=True)
    for file in sorted(source.glob("*.in")):
        result = forecast(json.loads(file.read_text()))
        (output / (file.stem + ".out")).write_text(json.dumps(result, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
