"""Assemble recorded frames + voice clips into an MP4 with chapters and an SRT file."""
import json, subprocess, sys, wave
from pathlib import Path
import numpy as np

out = Path(sys.argv[1]).resolve()
dest = Path(sys.argv[2]).resolve()
tl = json.loads((out / "timeline.json").read_text())
t0, t_end = tl["t0"], tl["tEnd"]
frames = tl["frames"]
steps = tl["steps"]
total = t_end - t0 + 1.0

# ── video: variable-duration frame list relative to t0
rel = [(f["file"], f["t"] - t0) for f in frames]
start_idx = max([i for i, (_, t) in enumerate(rel) if t <= 0] or [0])
rel = rel[start_idx:]
lines = []
for i, (f, t) in enumerate(rel):
    t = max(t, 0.0)
    nxt = rel[i + 1][1] if i + 1 < len(rel) else total
    d = max(nxt - t, 0.001)
    lines.append(f"file '{f}'\nduration {d:.4f}")
lines.append(f"file '{rel[-1][0]}'")
(out / "frames.txt").write_text("\n".join(lines) + "\n")
print("first frame offset", rel[0][1], "frames", len(rel), "total", total)

# ── audio
SR = 24000
buf = np.zeros(int(total * SR) + SR, dtype=np.float32)
for s in steps:
    with wave.open(s["wav"]) as w:
        assert w.getframerate() == SR and w.getnchannels() == 1
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    i = int((s["start"] + 0.15) * SR)
    buf[i:i + len(a)] += a
peak = np.abs(buf).max()
buf = buf / peak * 0.89
with wave.open(str(out / "voice.wav"), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((buf * 32767).astype(np.int16).tobytes())

# ── chapters
def ts(x):
    x = max(0, x); return f"{int(x // 60)}:{int(x % 60):02d}"
chapters = [(s["start"], s["chapter"]) for s in steps if s["isChapterStart"]]
meta = [";FFMETADATA1", "title=How to use Jane Avenue"]
for k, (st, name) in enumerate(chapters):
    en = chapters[k + 1][0] if k + 1 < len(chapters) else total
    meta += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(st * 1000)}", f"END={int(en * 1000)}", f"title={name}"]
(out / "meta.txt").write_text("\n".join(meta) + "\n")

# ── subtitles
def srt_t(x):
    ms = int(round(x * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s_, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s_:02d},{ms:03d}"
srt = []
for k, s in enumerate(steps):
    st = s["start"] + 0.15
    en = min(st + s["dur"] + 0.3, steps[k + 1]["start"] if k + 1 < len(steps) else total)
    srt.append(f"{k + 1}\n{srt_t(st)} --> {srt_t(en)}\n{s['say']}\n")
dest.mkdir(parents=True, exist_ok=True)
(dest / "jane-avenue-walkthrough.srt").write_text("\n".join(srt))
(out / "chapters.json").write_text(json.dumps([{"start": st, "ts": ts(st), "chapter": n} for st, n in chapters], indent=1))

mp4 = dest / "jane-avenue-walkthrough.mp4"
cmd = ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(out / "frames.txt"),
       "-i", str(out / "voice.wav"), "-i", str(out / "meta.txt"), "-map_metadata", "2", "-map_chapters", "2",
       "-map", "0:v", "-map", "1:a",
       "-vf", "fps=30,scale=1920:1200:flags=lanczos,format=yuv420p,fade=t=in:st=0:d=0.6",
       "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-tune", "stillimage",
       "-c:a", "aac", "-b:a", "128k", "-af", f"afade=t=out:st={total - 1.5:.2f}:d=1.5",
       "-t", f"{total:.2f}", "-movflags", "+faststart", str(mp4)]
subprocess.run(cmd, check=True)
print("wrote", mp4)
for st, n in chapters: print(ts(st), n)
