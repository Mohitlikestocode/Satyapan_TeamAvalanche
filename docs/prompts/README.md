# Prompts

Each person copies the text below the line of their file into Claude Code (opened in an empty folder), and answers its first question (their git name and email).

| File | Person | Branch |
|---|---|---|
| `A-models-eval.md` | the person with the GPU | `feat/models-eval` |
| `B-community.md` | one of the other two | `feat/community` |
| `C-traction.md` | the other one | `feat/traction` |

Rules for everyone: work only on your branch, only in your own files, commit under your own name (no AI credit lines; the hook rejects them), push every 30 minutes.

Integrator (repo owner): at about 23:00, 03:00 and 07:00 IST run

```bash
git fetch origin
git checkout main && git pull
git merge --no-ff origin/feat/models-eval
git merge --no-ff origin/feat/community
git merge --no-ff origin/feat/traction
python -m pytest -p no:warnings && git push origin main
```

A conflict means someone edited a file that is not theirs: look at `git diff --name-only` for that branch against `split-base`, ask them to undo it, and apply any real need yourself. Everyone then runs `git fetch origin && git merge origin/main` on their branch.
