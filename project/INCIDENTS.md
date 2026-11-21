# Incident post-mortems

Every failure that cost work, lost a result or took the page down: what happened, why, how it was fixed, and what now stops it happening again. Blameless: the aim is the prevention, not the person. Index of all systems: [README.md](README.md).

**When to write one:** a run had to be discarded, a result was wrong or lost, the page was down for more than one health check while the laptop was on, or a secret or private file reached git. Write it within a day, while the details are fresh, and link it from the work log line.

## Index

| ID | Date | What | Impact | Status |
|---|---|---|---|---|
| [INC-001](#inc-001) | 2026-11-18 | Resuming VAE training on a Colab G4 GPU diverged twice | two Colab sessions lost; two days' delay to epoch 150 | closed |
| [INC-002](#inc-002) | 2026-10-21 | Detector v2b training ran out of memory at step 1,100 | one training run repeated | closed |

## INC-001

**Resuming VAE training on a Colab G4 GPU diverged twice.** 2026-11-18.

- **What happened.** V1 was resumed from its epoch-101 checkpoint on a Colab G4 GPU to reach epoch 150. Both attempts produced diverging losses; both were discarded and nothing was committed.
- **Impact.** Two Colab sessions and their compute units; epoch 150 was reached two days later (2026-11-20). No earlier result was affected: epoch 101 was untouched in its own folder.
- **Cause (most likely).** The whole batch of 5,772 images in one pass on the G4 GPU gave wrong results: its first step scored a reconstruction loss of 212 instead of 172, and training blew up three epochs later. At that size some tensors exceed 2^31 elements. PyTorch 2.14.1 on that runtime may also have contributed. Not proven further, because the runtime could not be reproduced.
- **Fix.** Resumed on a Colab A100 with micro-batches of 2,886 images (same maths, every tensor under 2^31 elements), which completed epoch 150 (EXP-010).
- **Prevention** (`65ab4c9`, `colab/train_V1_colab.ipynb`):
  - Cell 8b, a pre-flight check before every session: computes the next epoch's first step from `last.pt` with updates switched off, checks the checkpoint's SHA-256, and records the PyTorch version and micro-batch.
  - An epoch rollback guard: after each epoch, its losses are compared with the median of the 10 before it (reconstruction at most 5 % higher, KL at most 2×). A broken epoch is rolled back to `last_good.pt` and the run stops, so a blow-up can no longer overwrite the last good checkpoint.
  - The run refuses to continue with a different batch configuration.

## INC-002

**Detector v2b training ran out of memory at step 1,100.** 2026-10-21.

- **What happened.** Training ridgenet-v2b on the laptop stopped with a NumPy memory error while building spectrograms (`models/detector/_failed/ridgenet-v2b_oom_at_step1100/train.log`).
- **Impact.** One training run repeated; v2b was then trained to completion and compared (EXP-001).
- **Cause.** Too little free memory on the laptop during data generation alongside other work.
- **Fix.** Rerun with the laptop otherwise idle.
- **Prevention.** Failed runs are kept in `models/detector/_failed/` with their log instead of being deleted, so a repeat failure is recognisable. Long runs start with the laptop otherwise idle.

## Template

```
## INC-0NN

**<One-line title.>** YYYY-MM-DD.

- **What happened.** <what was seen, when, by whom>
- **Impact.** <work lost, results affected, time down>
- **Cause.** <the root cause; say "most likely" when it is not proven>
- **Fix.** <what restored things>
- **Prevention.** <what now stops it happening again: a check, a test, a guard, a rule; with the commit>
```
