# Project instructions

## Work log: `WORKLOG.md`

`WORKLOG.md` at the repository root is the project's single work log: what is planned, what waits on the owner, and what has been done, across the whole project (reproduction, WhistleCode, detector paper, web page, deployment, repository).

- **Every change** to the project (code, configs, docs, models, results, web page, data records) is logged in the same turn as the change. Add one plain-English line under today's date in **Done** (newest date first), naming the area and the files or folders touched. Add the date heading if it is missing.
- **Planned work** goes into **To do** with an ID before it starts (reuse the area prefixes there: YOU, WC, DET, REP, WEB, OPS). Tick an item `[x]` when it is finished and log it under Done.
- **Things only the owner can do** (approvals, downloads, volunteers, commits, decisions) go under "Waiting on you".
- **Snapshot.** Keep "At a glance" and the "Updated" date current when the picture changes.
- **Old entries are never rewritten.** Correct them with a new dated line.
- **Commits.** When giving the owner commit commands, include `WORKLOG.md` in `git add`. The optional pre-commit check in `.githooks/` refuses commits without it.
