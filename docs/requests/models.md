# Core change requests from workstream A (models)

## 1. `.gitignore`: the bare `models/` rule hides workstream A's own folders

Line 16 of `.gitignore` is `models/`. It matches every folder named `models`, including `tests/models/` and
`web/templates/ext/models/`, which `docs/WORK_SPLIT.md` gives to workstream A. Weights live in `var/models/`, which `var/` already ignores.

Request: change line 16 from `models/` to `/models/` (root only), or delete it.
Workaround meanwhile: those files were added with `git add -f`; once tracked, git keeps tracking them.

## 2. `tests/test_api.py::test_voice_still_points_to_a_labelled_sample` (informational)

The voice handler (`plugins/models_voice.py`) now gives a real result when the server has ffmpeg and the Whisper model in
`var/models/faster-whisper-small/`. Without them it returns `None`, and the core route falls back to the labelled sample, so this
test still passes in CI. On the demo server (voice stack installed) a voice upload returns `mode: "engine"`.
No change needed now; if the test ever runs with the voice stack installed, it should accept `mode == "engine"` too.

## 3. Core `/check` page: link voice notes to the transcript-first page (optional)

`/models/voice` shows the transcript for the visitor to correct before checking, as the `/check/voice` design promises.
If you want the core check form to use it, point its voice option to `/models/voice`. The plain API path works without this.
