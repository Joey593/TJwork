# TJwork project instructions

This repository is the canonical home for the Aurora Test graduation project.
The user explicitly requested that future file creation and modifications for
this project happen in the TJwork GitHub checkout.

- Work inside this repository. In the current cloud session its location is
  `/workspace/TJwork`; use the actual checkout root if another session clones it
  elsewhere. `/workspace/work/aurora-test` is a compatibility symlink here.
- Keep source, documentation, workflows and reproducible experiment evidence in
  Git. The owner explicitly confirmed that this repository remains public and
  authorized committing this project's runtime credentials. The root `.env` is
  versioned under that instruction. Keep database contents, browser downloads,
  dependency directories and temporary caches untracked.
- Preserve the Vue 3 / FastAPI / MySQL / Playwright / pytest architecture.
- AI-generated cases require schema validation and explicit human review before
  platform execution. Editing an approved case must invalidate its approval.
- Do not fabricate LLM results, test outcomes, measurements or human review data.
  Distinguish real model calls, rules baselines and mocked interface tests.
- Inspect `git status` before changes. Preserve existing user edits. Validate
  relevant changes using the commands documented in README.md.
- Commit and synchronize completed project changes to this repository when
  authorized by the user's task. Do not claim GitHub synchronization before the
  remote commit is verified; do not force-push or change repository visibility.
- Cloud environment selection is separate from Git synchronization. Do not claim
  that cloning this repository changes the default environment for new chats.
