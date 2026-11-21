# Project instructions

## Work log: `WORKLOG.md`

`WORKLOG.md` at the repository root is the project's single work log: what is planned, what waits on the owner, and what has been done, across the whole project (reproduction, WhistleCode, detector paper, web page, deployment, repository).

- **Every change** to the project (code, configs, docs, models, results, web page, data records) is logged in the same turn as the change. Add one plain-English line under today's date in **Done** (newest date first), naming the area and the files or folders touched. Add the date heading if it is missing.
- **Planned work** goes into **To do** with an ID before it starts (reuse the area prefixes there: YOU, WC, DET, REP, WEB, OPS). Tick an item `[x]` when it is finished and log it under Done.
- **Bugs** go under "Bugs" as `BUG-n`, with how to make them happen and how bad they are.
- **Things only the owner can do** (approvals, downloads, volunteers, commits, decisions) go under "Waiting on you".
- **Snapshot.** Keep "At a glance" and the "Updated" date current when the picture changes.
- **Old entries are never rewritten.** Correct them with a new dated line.
- **Commits.** When giving the owner commit commands, include `WORKLOG.md` in `git add`. The pre-commit hook in `.githooks/` refuses commits without it, and refuses staged secrets and lint errors.

## Engineering systems: `project/`

The project's engineering systems are indexed in `project/README.md`. Keep them current in the same turn as the work, like the work log.

- **Start of a session:** follow `project/HANDOVER.md` (read "At a glance", `git status`, `python tools/repo.py check --quick`).
- **Before giving commit commands:** run `python tools/repo.py check`, review the diff (`project/WORKFLOW.md`, "Code review"), and walk the Definition of Done in `project/WORKFLOW.md`. Say what was reviewed and what was found.
- **Registers to update when they apply:** an experiment or run → `project/EXPERIMENTS.md` (row before it starts); a model file → `project/MODELS.md` and `python tools/repo.py checksums make`; a reported number or claim → `project/TRACEABILITY.md`; a project-level choice → `project/DECISIONS.md`; a failure that cost work → `project/INCIDENTS.md`; a user-visible change → `[Unreleased]` in `CHANGELOG.md`; a new dependency → its requirements file, `project/LICENSING.md`, `python tools/repo.py lock`; a new or moved document → `docs/INDEX.md`; a new component, command or route → `docs/ARCHITECTURE.md`.
- **Releases** follow `project/RELEASES.md`; the version lives only in `pyproject.toml`.
