# Walkthrough video recorder

These scripts produce `jane-avenue-walkthrough.mp4`, the narrated tour of the Jane Avenue website. The notes that go with it are in [`docs/WALKTHROUGH_VIDEO_NOTES.md`](../../docs/WALKTHROUGH_VIDEO_NOTES.md).

The video is not committed, because the repository does not accept files over 5 MB. Rebuild it with the steps below.

| File | Purpose |
|---|---|
| `steps.js` | The script: each step is one subtitle and voice line, plus the clicks and highlights that go with it |
| `overlay.js` | Injected into the page: subtitles, cursor, highlight boxes and title cards |
| `speak.js` | Turns subtitle text into words the speech engine reads unambiguously (`£7.0bn` becomes "seven billion pounds", `2027-28` becomes "twenty twenty-seven to twenty-eight") |
| `record.js` | Drives the site with Playwright, captures frames over CDP and logs the timings. `--dry` takes one screenshot per step instead |
| `build.py` | Combines the frames and voice clips into an MP4 with chapters, and writes an `.srt` file |

## Requirements
- Node with Playwright and Chromium, Python with numpy, `ffmpeg`, and `RHVoice-test` with the `alan` voice (`apt-get install rhvoice rhvoice-english`).
- Run the backend in cached mode on a **fresh database**, so that History only shows the walkthrough's analyses, and run the frontend dev server:

```bash
JANE_MODE=cached PYTHONPATH=backend JANE_DB_PATH=/tmp/jane-walkthrough.db .venv/bin/python -m uvicorn jane_avenue.api.app:app --port 8000
```

```bash
cd frontend && npm run dev
```

## Run

```bash
cd scripts/walkthrough-video && node record.js out --dry
```

```bash
cd scripts/walkthrough-video && node record.js out
```

```bash
cd scripts/walkthrough-video && python build.py out deliver
```

The figures in `steps.js` were read from the site on 8 November 2026. A query with no date defaults to 1 April of the following calendar year, so a recording made on or after 1 January 2027 shows figures shifted by a year. In that case, re-read the figures from the site and update the narration before recording.
