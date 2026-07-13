# TripleHiggsTopEffects

This repository contains the small, reproducible orchestration layer for
generating parton-level LHE samples for

```text
g g > h h h
```

with MadGraph5_aMC@NLO and the `heft_loop_sm_restricted5` UFO model.  It is
deliberately separate from MadGraph itself, the UFO source checkout, generated
process directories, and event files.

## Physics conventions

The restricted UFO uses the following names in `BLOCK BSMINPUTS`:

| Scan name | UFO name | LHA code |
|---|---|---:|
| `ct1` | `CT1` | 993 |
| `ct2` | `CT2` | 994 |
| `ct3` | `CT3` | 995 |
| `k3 = 1 + c3` | `D3` | 996 |
| `k4 = 1 + d4` | `D4` | 997 |

The campaign driver supports two families:

- `ct2`: vary `(k3, k4, ct2)`, fix `CT1=1` and `CT3=0`;
- `ct3`: vary `(k3, k4, ct3)`, fix `CT1=1` and `CT2=0`.

The UFO's `D3` and `D4` parameters multiply the SM triple- and quartic-Higgs
vertices directly, so CSV inputs are `k3` and `k4`, not the shifted anomalous
coefficients.  For example, `(k3, k4) = (-8, 50)` is written as
`D3=-8, D4=50`.  This agrees with the convention in
[arXiv:2312.13562](https://arxiv.org/abs/2312.13562).

`--ct1` can override the `CT1=1` convention explicitly.  Every run writes all
five couplings into the parameter card, so it never inherits the UFO's
illustrative defaults.

The preparation script generates

```text
g g > h h h [noborn=QCD MHEFT] MHEFT^2<=6
```

as recommended for the restricted model.

## Tiresias layout

The working tree is expected at

```text
/mnt/ssd2/Projects/TripleHiggsTopEffects
```

The following pre-existing paths are runtime dependencies and are ignored by
Git:

```text
MG5_aMC_v3_5_16/
MG5_aMC_v3.5.16.tar.gz
multihiggs_loop_sm/
```

The current process directory is
`MG5_aMC_v3_5_16/gg_hhh_restricted5`.  Generated LHE files are copied to
`artifacts/lhe/`; both the MadGraph event directories and `artifacts/` remain
untracked.

## Prepare a process

The existing Tiresias process is already prepared.  On a fresh installation,
run:

```bash
python3 scripts/prepare_process.py --dry-run
python3 scripts/prepare_process.py
```

Defaults assume the Tiresias layout above.  Use `--mg5-root`, `--model-source`,
or `--process-dir` for another layout.  Add `--install-collier` only when the
MadGraph installation still needs Collier and has network access.

## Define and run scans

The CSV files in `scans/` are deliberately small examples, not production
benchmark choices.  Copy and edit them to define the desired points; scan
definitions are suitable for version control.

Always inspect a dry run first:

```bash
python3 scripts/run_scan.py \
  --scan ct2 \
  --points scans/ct2.example.csv \
  --events 1000 \
  --cores 8 \
  --dry-run
```

Remove `--dry-run` to generate events.  The corresponding `ct3` invocation is:

```bash
python3 scripts/run_scan.py \
  --scan ct3 \
  --points scans/ct3.example.csv \
  --events 1000 \
  --cores 8 \
  --dry-run
```

The default beam energy is 6.8 TeV per proton (13.6 TeV collisions), matching
the process currently on Tiresias.  The driver preserves the process
directory's PDF and scale choices unless `--pdlabel`, `--lhaid`, and/or
`--dynamical-scale-choice` are supplied. Review those choices before a
production campaign.

## 13 TeV production campaign

The tracked production grids contain:

- 16 `ct2` jobs: four `(k3,k4)` points times four `ct2` values, with `CT3=0`;
- 8 `ct3` jobs: four `(k3,k4)` points times two `ct3` values, with `CT2=0`.

This is 24 production jobs and 240,000 requested events.  The serial launcher
uses 6.5 TeV per beam, explicitly constrains MadGraph to one core,
`NNPDF40_lo_as_01180` (LHAPDF ID 331900), and
MadGraph dynamical-scale choice 3.  The LO PDF is the selected campaign setup;
the scale choice follows the simulation setup documented in arXiv:2312.13562.
The launcher loads `herwig/stable-full-py3-rivet4` and then prepends MadGraph's
own `HEPTools/lib` directory so that MadLoop can resolve its Collier library.
The driver writes both per-beam PDF labels explicitly, as required by the
MadGraph 3.5.x run-card validity logic used by this generated process.
The launcher first generates a separate 10-event pilot and starts production
only if the pilot succeeds:

```bash
scripts/run_13tev_serial.sh
```

The launcher is restartable: completed runs are verified and reused.  Set
`SKIP_SMOKE=1` only after a valid pilot already exists.  `DRY_RUN=1` prints and
validates the complete campaign plan without starting MadGraph.

Runs stop at parton level.  Each successful LHE is copied to `artifacts/lhe/`
and recorded in `artifacts/lhe/manifest.jsonl` with its couplings, checksum,
cross section, event count, and repository revision.  Existing run names are
never overwritten by default:

- `--resume` verifies and reuses a matching completed MadGraph run;
- `--force` explicitly allows MadGraph to reuse an existing run name.

The driver locks the shared process directory and restores its original
`param_card.dat` and `run_card.dat` even after an ordinary failure or interrupt.
Run only one campaign against a given process directory at a time.

## Tests

The local tests exercise CSV validation and card rewriting without requiring
MadGraph:

```bash
python3 -m unittest discover -s tests -v
```
