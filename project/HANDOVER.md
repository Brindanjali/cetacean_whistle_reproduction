# Handover

How either of us picks the work up cold: at the start of a session, on a new machine, or after a break. Index of all systems: [README.md](README.md).

## Start of every session (5 minutes)

1. **Read the state:** [`WORKLOG.md`](../WORKLOG.md), "At a glance" (what is next), "Waiting on you" and "Bugs".
2. **See what changed:** `git status` and `git log --oneline -10`. Uncommitted work belongs to the last session's last Done entry.
3. **Check health:** `python tools/repo.py check --quick` (everything but the test suites, under a minute).
4. **Claude also reads** `CLAUDE.md` and its memory, and checks that any file or flag a memory names still exists.

## End of every session

1. Every change has its line under today's date in `WORKLOG.md` "Done". "At a glance" and "Updated" are current.
2. Work in progress is a To do item with its state written down, so the next session can continue it without this conversation.
3. `python tools/repo.py check` passes, or the failure is written down as a BUG item.
4. Claude gives the owner the commit commands (`git add` always includes `WORKLOG.md`); the owner commits and pushes.

## Who does what

| The owner | Claude |
|---|---|
| decides; approves anything outward-facing or hard to undo | proposes, with a recommendation; decides details the owner left open and tags them `[DECISION]` |
| commits, pushes, tags releases | writes the code, docs and registers; gives exact commit commands |
| downloads, accounts, volunteers, the mentor, licences | lists exactly what is needed under "Waiting on you" |
| runs Colab sessions and anything on other machines | prepares notebooks, scripts and checklists for them |

## A new machine

```
git clone https://github.com/anonymus-k-dot/cetacean_whistle_reproduction.git
cd cetacean_whistle_reproduction
pip install -r requirements.txt -r whistlecode/requirements.txt -c constraints.txt
git config core.hooksPath .githooks
python tools/repo.py check
```

That gives the code, both VAE checkpoints and all records. The raw audio, the dataset, the GMMs, the codebook and the WhistleCode outputs are not in git: [STORAGE.md](STORAGE.md) says where each comes from and how to rebuild it, and `python tools/repo.py checksums verify` confirms the result.

## Easy to get wrong

- **Model 1 is Nyx (epoch 101).** Don't refresh `models/vaegmm/V1_L64_b1e-4_critic_E191/` to epoch 150; Delphi lives in its own folder ([D-007](DECISIONS.md#d-007)).
- **Encounter 276 is the test set.** Nothing is tuned on it; development uses 214 ([D-009](DECISIONS.md#d-009)). Campaign v2's seed 20261205 is reserved.
- **Pass marks are frozen** (`whistlecode/PLAN.md` 8.7), and a failure stays a failure ([D-010](DECISIONS.md#d-010)).
- **`[paper]` values are locked**; the loaders refuse a change.
- **Nothing is overwritten:** runs, fits, datasets, campaigns and model files get new folders.
- **The page is desktop-only** ([D-015](DECISIONS.md#d-015)); its controls stay minimal.
- **Run commands from the repository root.** On Windows, use `python` (not `python3`, which may be the Store placeholder).
- **Git is the owner's:** Claude never commits or pushes.
- **`docs/private/` never goes into git**, and neither does anything that looks like a key (the hook refuses it).

## Where to look

| Question | Answer in |
|---|---|
| What is this project, and what are its results? | `README.md` |
| What happens next, and what is blocked on whom? | `WORKLOG.md` |
| How do the parts fit together? | `docs/ARCHITECTURE.md` |
| Which document is the authority on X? | `docs/INDEX.md` |
| Why was it done this way? | `project/DECISIONS.md`, then the inline `[DECISION]` tags |
| Where does this number come from? | `project/TRACEABILITY.md` |
| Which model file is which? | `project/MODELS.md` |
| How do I release or deploy? | `project/RELEASES.md` |
