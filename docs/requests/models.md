# Core change requests from workstream A (models)

## 1. `.gitignore`: the bare `models/` rule hides workstream A's own folders

Line 16 of `.gitignore` is `models/`. It matches every folder named `models`, including `tests/models/` and
`web/templates/ext/models/`, which `docs/WORK_SPLIT.md` gives to workstream A. Weights live in `var/models/`, which `var/` already ignores.

Request: change line 16 from `models/` to `/models/` (root only), or delete it.
Workaround meanwhile: those files were added with `git add -f`; once tracked, git keeps tracking them.
