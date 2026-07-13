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
the repository needs a MadGraph installation and a copy of the restricted UFO.
Inspect the proposed paths and MadGraph command deck first:

```bash
python3 scripts/prepare_process.py \
  --mg5-root /path/to/MG5_aMC_v3_5_16 \
  --model-source /path/to/heft_loop_sm_restricted5 \
  --dry-run
```

Remove `--dry-run` to copy the UFO into MadGraph and generate the process.  Use
`--process-dir /path/to/process` when the generated process should not live at
`MG5_aMC_v3_5_16/gg_hhh_restricted5`.  Add `--install-collier` only when the
MadGraph installation still needs Collier and has network access.  The default
paths reproduce the Tiresias layout above, so the short form there is:

```bash
python3 scripts/prepare_process.py --dry-run
python3 scripts/prepare_process.py
```

Another computer must provide Python, working C/C++ and Fortran compilers,
MadGraph's loop dependencies (including Collier), LHAPDF, and the requested PDF
set.  Activate that machine's module, package-manager, or local installation so
that `lhapdf-config` and the corresponding shared libraries are available
before running a scan.  The current setup is tested with MadGraph 3.5.16.

## Define scan points

Scan points are ordinary CSV files and are suitable for version control.  Each
row defines one MadGraph job, and rows are processed sequentially.  A `ct2`
file must have exactly the columns `name,k3,k4,ct2`; the driver fixes `CT3=0`:

```csv
name,k3,k4,ct2
point_a,-8,50,-0.3
point_b,-8,50,0.6
sm_reference,1,1,0
```

A `ct3` file uses `name,k3,k4,ct3`; the driver fixes `CT2=0`:

```csv
name,k3,k4,ct3
point_a,-8,50,-5
point_b,-8,50,5
sm_reference,1,1,0
```

Point names must be unique within a file, may contain only letters, numbers,
and underscores, and must not start with an underscore.  They become part of
the MadGraph run name.  Use new names when changing the couplings, energy,
event count, PDF, or scale of a previously attempted campaign.

The CSV values are the direct multipliers `k3` and `k4`.  Convert anomalous
parameters before writing the file: `k3=1+c3` and `k4=1+d4`.  The files
`scans/ct2.example.csv` and `scans/ct3.example.csv` provide minimal templates.

## Run a custom scan on Tiresias

Load the environment once in the shell that will run MadGraph:

```bash
cd /mnt/ssd2/Projects/TripleHiggsTopEffects

source /etc/profile.d/modules.sh
module load herwig/stable-full-py3-rivet4

export LD_LIBRARY_PATH="$PWD/MG5_aMC_v3_5_16/HEPTools/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
```

Then inspect a dry run.  For example, this is a serial 14 TeV `ct2` scan with
20,000 events per point and NNPDF 4.0 LO:

```bash
python3 scripts/run_scan.py \
  --scan ct2 \
  --points scans/my_ct2.csv \
  --events 20000 \
  --cores 1 \
  --ebeam 7000 \
  --ct1 1 \
  --pdlabel lhapdf \
  --lhaid 331900 \
  --dynamical-scale-choice 3 \
  --mg5-root "$PWD/MG5_aMC_v3_5_16" \
  --output-dir "$PWD/artifacts/lhe/my_14tev_scan" \
  --dry-run
```

`--ebeam` is the energy of each proton, not the total collision energy.  Common
choices are:

| Proton energy (`--ebeam`) | Proton-proton energy |
|---:|---:|
| 6500 GeV | 13 TeV |
| 6800 GeV | 13.6 TeV |
| 7000 GeV | 14 TeV |
| 50000 GeV | 100 TeV |

Remove `--dry-run` to generate events.  To run `ct3`, change both `--scan ct2`
and the points file:

```bash
python3 scripts/run_scan.py \
  --scan ct3 \
  --points scans/my_ct3.csv \
  --events 20000 \
  --cores 1 \
  --ebeam 7000 \
  --ct1 1 \
  --pdlabel lhapdf \
  --lhaid 331900 \
  --dynamical-scale-choice 3 \
  --mg5-root "$PWD/MG5_aMC_v3_5_16" \
  --output-dir "$PWD/artifacts/lhe/my_14tev_ct3"
```

Before a full campaign, run a one-row CSV with a distinct name such as
`smoke_point_a` and a small event count.  Check that it produces a nonempty
LHE, that the banner records the intended couplings, beam energy, PDF, and
scale, and that `manifest.jsonl` reports the requested event count.  Keep smoke
and production names distinct because changing `--events` makes them different
runs.

The principal command-line settings are:

| Option | Meaning |
|---|---|
| `--events N` | Requested events for every CSV row |
| `--cores N` | MadGraph cores used for the current point |
| `--ebeam E` | Energy of each proton in GeV |
| `--ct1 X` | `CT1` value; normally 1 |
| `--seed-start N` | Assign consecutive explicit seeds starting at `N` |
| `--pdlabel lhapdf --lhaid ID` | Select an installed LHAPDF set |
| `--dynamical-scale-choice N` | Override the MadGraph scale choice |
| `--mg5-root PATH` | MadGraph installation containing the process |
| `--process-dir PATH` | Explicit generated-process directory |
| `--output-dir PATH` | Destination for copied LHE files and the manifest |
| `--dry-run` | Print the campaign plan without launching MadGraph |
| `--resume` | Validate and reuse completed, exactly matching runs |

Points remain sequential even when `--cores` is larger than one; the option
parallelizes MadGraph work within the current point.  Run only one campaign at
a time against a given generated-process directory.  The process lock prevents
accidental concurrent use.

The driver preserves the generated process's PDF and scale unless overrides
are supplied.  `--pdlabel` and `--lhaid` must be given together, and the PDF
must be installed in the active LHAPDF data path.  NNPDF 4.0 LO in the current
Tiresias setup is `NNPDF40_lo_as_01180`, LHAPDF ID 331900.

Prefer a new point name when changing a setup.  Use `--resume` only for a
genuinely identical run: it checks the couplings, event count, beam energy,
seed, PDF, and scale before reusing the LHE.  `--force` deliberately bypasses
the existing-run protection and should be reserved for controlled recovery.

## Run in `screen`

Long runs should live in a persistent terminal on Tiresias:

```bash
screen -S hhh_my_scan
```

Run the environment setup and `run_scan.py` command inside that session.  Type
`Ctrl-A`, then `D`, to detach.  Reconnect with:

```bash
screen -r hhh_my_scan
```

Runs stop at parton level.  MadGraph retains its run under
`gg_hhh_restricted5/Events/`, while the driver copies the completed LHE to the
chosen `--output-dir`.  The same directory receives `manifest.jsonl`, including
the couplings, event count, cross section, PDF and scale settings, checksum,
and repository revision.

## Run a custom scan on another computer

After preparing a process and activating that computer's LHAPDF/compiler
environment, use the same driver with explicit paths:

```bash
python3 scripts/run_scan.py \
  --scan ct2 \
  --points scans/my_ct2.csv \
  --events 10000 \
  --cores 1 \
  --ebeam 6500 \
  --ct1 1 \
  --pdlabel lhapdf \
  --lhaid 331900 \
  --dynamical-scale-choice 3 \
  --process-dir /path/to/gg_hhh_restricted5 \
  --output-dir /path/to/output
```

Replace LHAPDF ID 331900 if that machine uses another installed set.  The
driver automatically invokes the tracked MadEvent compatibility wrapper; do
not call the generated `bin/generate_events` executable directly for these
LHAPDF scans.

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
It also runs MadEvent through a compatibility wrapper that repairs a MadLoop
second-pass bug which otherwise resets only the generated Fortran global PDF
label to MadGraph's built-in default.  The wrapper changes the transient
`run_card.inc`; it does not modify the MadGraph installation or model.
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
