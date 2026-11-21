# Workflow: tasks, Definition of Done, code review

How a piece of work goes from an idea to a commit. Index of all systems: [README.md](README.md).

```
To do item (ID) -> work -> python tools/repo.py check -> review -> Definition of Done -> WORKLOG line -> commit commands -> owner commits
```

## Task tracker

The tracker is the **To do** section of [`WORKLOG.md`](../WORKLOG.md). There is one list for the whole project.

- **Every piece of planned work gets an ID before it starts:** YOU (only the owner can do it), WC (WhistleCode), DET (detector paper), REP (reproduction), WEB (page and deployment), OPS (repository and engineering). IDs are never reused or renumbered.
- **Bugs** go under "Bugs" as `BUG-n`, with: what happens, how to make it happen, how bad it is (high: wrong results or a broken page; medium: a feature fails with a workaround; low: cosmetic), and the area. A fixed bug is ticked and logged under Done like any task.
- **One item is "Next."** The "At a glance" table names it.
- **Waiting on the owner:** anything that needs the owner (an approval, a download, a decision, volunteers, a commit) goes under "Waiting on you", with what exactly to do.
- **Done means ticked and logged.** Tick `[x]`, then add a line under today's date in Done naming the files.
- **Dropped work** moves to "Decided not to do", with the date and the reason. A project-level choice also gets a decision record ([DECISIONS.md](DECISIONS.md)).

## Definition of Done

A change is done only when every line that applies is true. Claude checks this list before giving commit commands.

**Always**

- [ ] `python tools/repo.py check` passes (lint, config, secrets, links, checksums, both test suites).
- [ ] A plain-English line under today's date in `WORKLOG.md` names the area and the files.
- [ ] The diff has been reviewed ([Code review](#code-review)) and every finding is fixed or recorded.
- [ ] No secret, no file from `docs/private/`, and nothing over 50 MB is staged.

**When it applies**

- [ ] **New behaviour:** a test proves it. **A bug fix:** a test fails before the fix and passes after it.
- [ ] **A changed command, route or file layout:** `README.md`, `docs/TECHNICAL_REFERENCE.md` and `docs/ARCHITECTURE.md` say so.
- [ ] **A new or changed setting:** it has an evidence tag (`[EXPLICIT]`, `[DECISION]`, ...) and a comment in its TOML file. A `[paper]` value is never changed.
- [ ] **A choice between alternatives that later work depends on:** a decision record in [DECISIONS.md](DECISIONS.md).
- [ ] **A run or experiment:** a row in [EXPERIMENTS.md](EXPERIMENTS.md), with the commit, seed and output folder.
- [ ] **A new or changed model file:** [MODELS.md](MODELS.md) updated and `python tools/repo.py checksums make` run.
- [ ] **A new reported number or verdict:** a row in [TRACEABILITY.md](TRACEABILITY.md) pointing at the record that holds it.
- [ ] **A user-visible change:** a line under `[Unreleased]` in [`CHANGELOG.md`](../CHANGELOG.md).
- [ ] **Something broke and cost work:** an entry in [INCIDENTS.md](INCIDENTS.md).
- [ ] **A new dependency:** added to the right requirements file, with its licence in [LICENSING.md](LICENSING.md), and `python tools/repo.py lock` run.

## Code review

Every change is reviewed before the commit commands are given. The project has one author and one engineer, so the engineer reviews its own diff with fresh eyes and the owner approves.

**How**

1. Claude runs a review of the whole diff (`/code-review`, or reads `git diff` line by line for a small change).
2. Each finding is fixed in the same change, or recorded: as a BUG item, or as a "known limitation" in the README if it is accepted.
3. The summary given to the owner says what was reviewed and what was found, including "nothing found".

**What the review looks for**

| Area | Questions |
|---|---|
| Correctness | Does it do what the task says? Edge cases: empty input, one item, the largest file, a missing file? |
| Research integrity | Is any paper value changed? Is a development encounter used for testing, or the test encounter (276) used for tuning? Is a failed pass mark reported as failed? |
| Lineage | Do new outputs record their config hash, commit and input hashes? Does anything overwrite an existing run, fit or dataset? |
| Tests | Is the new behaviour tested? Would the test fail if the code were wrong? |
| Security | Any secret, any new upload or file route, any path built from user input? (`.github/SECURITY.md`) |
| Simplicity | Is there an existing helper for this? Can it be shorter without losing clarity? |
| Docs | Do the README, the technical reference and the registers still tell the truth? |
