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
| `c3` | `D3` | 996 |
| `d4` | `D4` | 997 |

The campaign driver supports two families:

- `ct2`: vary `(c3, d4, ct2)`, fix `CT1=1` and `CT3=0`;
- `ct3`: vary `(c3, d4, ct3)`, fix `CT1=1` and `CT2=0`.

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
directory's PDF and scale choices unless `--pdlabel` and `--lhaid` are supplied.
Review those choices before a production campaign.

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
