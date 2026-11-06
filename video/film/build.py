"""Build index.html for the Airlock demo film from the voiceover clips.

    python video/film/build.py

Each scene lasts as long as its narration clip (assets/vo/sN.wav) plus a lead-in and a
tail, so the picture always follows the voice. Captions are split from the same lines.
Every number and identifier on screen comes from docs/evidence/run-3.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEAD, TAIL, END_HOLD = 0.3, 0.4, 2.5
MAX_WORDS = 8


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def chunks(line: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"(?<=[.,?])\s+", line) if p.strip()]
    out: list[str] = []
    for p in parts:
        words = p.split()
        while len(words) > MAX_WORDS:
            out.append(" ".join(words[:MAX_WORDS]))
            words = words[MAX_WORDS:]
        if out and len(words) < 3:
            out[-1] = f"{out[-1]} {' '.join(words)}"
        else:
            out.append(" ".join(words))
    return out


def caption_text(line: str) -> str:
    return line.replace("M L D S A sixty-five", "ML-DSA-65")


def main() -> None:
    lines = (HERE / "assets/vo/lines.txt").read_text(encoding="utf-8").splitlines()
    scenes, captions, audio = [], [], []
    t = 0.0
    for i, line in enumerate(lines, start=1):
        vo = duration(HERE / f"assets/vo/f{i}.wav")
        d = LEAD + vo + TAIL + (END_HOLD if i == len(lines) else 0)
        scenes.append({"t": round(t, 3), "d": round(d, 3)})
        audio.append(f'<audio id="vo{i}" class="clip" src="assets/vo/f{i}.wav" data-start="{t + LEAD:.3f}" '
                     f'data-duration="{vo:.3f}" data-track-index="20"></audio>')
        parts = chunks(caption_text(line))
        total = sum(len(p) for p in parts)
        c = t + LEAD
        for j, p in enumerate(parts):
            cd = vo * len(p) / total
            captions.append(f'<div id="cap{i}-{j}" class="clip cap" data-start="{c:.3f}" data-duration="{cd - 0.04:.3f}" '
                            f'data-track-index="10"><span>{p}</span></div>')
            c += cd
        t += d
    template = (HERE / "template.hf").read_text(encoding="utf-8")
    html = (template.replace("__TOTAL__", f"{t:.3f}")
            .replace("__SCENES_JSON__", json.dumps(scenes))
            .replace("__CAPTIONS__", "\n      ".join(captions))
            .replace("__AUDIO__", "\n      ".join(audio)))
    for i, s in enumerate(scenes, start=1):
        html = html.replace(f"__S{i}__", f'data-start="{s["t"]}" data-duration="{s["d"]}"')
    def video_slot(m: re.Match) -> str:
        i, off, dur = int(m.group(1)), float(m.group(2)), float(m.group(3))
        return f'data-start="{scenes[i - 1]["t"] + off:.3f}" data-duration="{dur:.3f}"'
    html = re.sub(r"__VS(\d+):([\d.]+):([\d.]+)__", video_slot, html)
    (HERE / "index.html").write_text(html, encoding="utf-8")
    print(f"index.html: {len(scenes)} scenes, {len(captions)} captions, {t:.1f}s")


if __name__ == "__main__":
    main()
