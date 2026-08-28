# TripleHiggsTopEffects

This repository contains the small, reproducible orchestration layer for
generating parton-level LHE samples for

```text
g g > h h h
```

with MadGraph5_aMC@NLO and the `heft_loop_sm_restricted5` UFO model.  The exact
restricted UFO used by the campaign is vendored under
`models/heft_loop_sm_restricted5/`.  MadGraph itself, generated process
directories, and event files remain deliberately separate from the repository.

## Physics conventions

The restricted UFO uses the following names in `BLOCK BSMINPUTS`:

| Scan name | UFO name | LHA code |
|---|---|---:|
| `ct1 = c_t1` | `CT1` | 993 |
| `ct2` | `CT2` | 994 |
| `ct3` | `CT3` | 995 |
| `c3 = k3 - 1` | `D3` | 996 |
| `d4 = k4 - 1` | `D4` | 997 |

The UFO contains the ordinary SM top-Yukawa vertex and a separate anomalous
vertex proportional to `CT1`.  Consequently,

```text
kappa_t = 1 + CT1
```

`CT1` is the anomalous shift `c_t1`, not the full top-Yukawa multiplier.
The SM top-Yukawa baseline is therefore `CT1=0`.  The campaign driver supports
two families:

- `ct2`: vary `(k3, k4, ct2)`, fix `CT1=0` and `CT3=0`;
- `ct3`: vary `(k3, k4, ct3)`, fix `CT1=0` and `CT2=0`.

The UFO contains separate ordinary-SM `hhh` and `hhhh` vertices and additional
MHEFT vertices proportional to its external inputs `D3` and `D4`.  Consequently,

```text
k3 = 1 + D3
k4 = 1 + D4
```

Here the UFO name `D3` is the anomalous cubic shift commonly denoted `c3`.
The SM self-coupling point is therefore `D3=0, D4=0`, corresponding to
`k3=k4=1`.  CSV inputs remain the physically labelled kappas `k3` and `k4`;
the driver performs the offset when writing `BLOCK BSMINPUTS`:

| Requested `(k3,k4)` | Card `(D3,D4)` |
|---:|---:|
| `(-8,50)` | `(-9,49)` |
| `(6,50)` | `(5,49)` |
| `(-5,-50)` | `(-6,-51)` |
| `(3,-50)` | `(2,-51)` |
| `(1,1)` | `(0,0)` |

These definitions follow the shifted-coupling convention in
[arXiv:2312.13562](https://arxiv.org/abs/2312.13562).

`--ct1` can override the `CT1=0` convention for a deliberate non-SM
top-Yukawa scan.  Every run writes all five couplings into the parameter card,
so it never inherits an old or externally supplied card value.

The preparation script generates

```text
g g > h h h [noborn=QCD MHEFT] MHEFT^2<=6
```

as recommended for the restricted model.

## Vendored loop model

The repository contains a ready-to-copy snapshot of
`heft_loop_sm_restricted5` in `models/heft_loop_sm_restricted5/`.  It was
exported from `git@gitlab.com:apapaefs/multihiggs_loop_sm.git` at commit
`99ba5ee9066943a727f063099053604ea2e2f102`.  See `models/README.md` for its
provenance and citation.

`scripts/prepare_process.py` uses this vendored directory by default and copies
it to `MG5_aMC_v3_5_16/models/heft_loop_sm_restricted5` when preparing a fresh
MadGraph process.  The separate `multihiggs_loop_sm/` checkout on Tiresias is
therefore no longer required for future process preparation.  To install only
the model manually, run:

```bash
cp -a models/heft_loop_sm_restricted5 /path/to/MG5_aMC_v3_5_16/models/
```

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
`artifacts/lhe/`; the MadGraph event directories and large LHE samples remain
untracked.  Compact manifests, fit results, and publication figures may be
version-controlled for provenance and reproducibility.

## Prepare a process

The existing Tiresias process is already prepared.  On a fresh installation,
the repository supplies the restricted UFO, so only a suitable MadGraph
installation is needed.  Inspect the proposed paths and MadGraph command deck
first:

```bash
python3 scripts/prepare_process.py \
  --mg5-root /path/to/MG5_aMC_v3_5_16 \
  --dry-run
```

Remove `--dry-run` to copy the vendored UFO into MadGraph and generate the
process.  Use `--model-source /path/to/another/UFO` only to override the
tracked snapshot deliberately.  Use `--process-dir /path/to/process` when the
generated process should not live at
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

The CSV values are the total multipliers `k3` and `k4`.  Convert anomalous
parameters before writing the file: `k3=1+c3` and `k4=1+d4`.  The driver then
writes `D3=k3-1` and `D4=k4-1` to the UFO card.  The files
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
  --ct1 0 \
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
  --ct1 0 \
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
| `--ct1 X` | Anomalous shift `CT1=c_t1`; default 0 gives `kappa_t=1` |
| `--seed-start N` | Assign consecutive explicit seeds starting at `N` |
| `--pdlabel lhapdf --lhaid ID` | Select an installed LHAPDF set |
| `--dynamical-scale-choice N` | Override the MadGraph scale choice |
| `--scalefact X` | Multiply the selected dynamical renormalization and factorization scales by `X` |
| `--survey-splitting N` | Explicit survey jobs per integration channel; mainly used by the parallel orchestrator |
| `--systematics` / `--no-systematics` | Enable or disable event-by-event scale and PDF weights |
| `--mg5-root PATH` | MadGraph installation containing the process |
| `--process-dir PATH` | Explicit generated-process directory |
| `--output-dir PATH` | Destination for copied LHE files and the manifest |
| `--dry-run` | Print kappas and their converted card inputs without launching MadGraph |
| `--resume` | Validate and reuse completed, exactly matching runs |

`run_scan.py` keeps points sequential even when `--cores` is larger than one;
the option parallelizes MadGraph work within the current point.  Run only one
campaign at a time against a given generated-process directory.  The process
lock prevents accidental concurrent use.  Use `run_parallel_scan.py`, described
below, when independent process copies should run concurrently.

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
the couplings, event count, cross section and integration error, PDF and scale
settings, checksum, and repository revision.

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
  --ct1 0 \
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

This is 24 production jobs and 2.4 million requested events.  Both production
launchers use 100,000 events per point and 6.5 TeV per beam.  The serial
launcher explicitly constrains MadGraph to one core per point.  The parallel
launcher distributes a machine-wide CPU budget across isolated process copies.
Both fix `CT1=0`, corresponding to `kappa_t=1`, and use
`NNPDF40_lo_as_01180` (LHAPDF ID 331900), and
MadGraph dynamical-scale choice 3.  The LO PDF is the selected campaign setup;
the scale choice follows the simulation setup documented in arXiv:2312.13562.
The production launcher disables MadGraph's automatic event-by-event
systematics weights, so the LHE files contain the requested central samples
without an additional PDF/scale weight ensemble.  Custom scans preserve the
process default unless `--systematics` or `--no-systematics` is supplied.
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

### Corrected 55-point campaign on Tiresias and Odysseus

The four tracked production/additional CSVs contain 55 unique samples in
total: 35 `ct2` points and 20 `ct3` points.  Both corrected launchers use their
`k3,k4` columns as kappas and write `D3=k3-1,D4=k4-1`.  Each host first runs a
10-event `(k3,k4)=(1,1)` pilot and validates that the banner contains
`CT1=CT2=CT3=D3=D4=0`.

The canonical list is partitioned into three deterministic modulo shards.
Tiresias takes shard 1 (18 points) and runs two 96-core points at a time on
192 logical CPUs.  Odysseus takes shards 0 and 2 (37 points) and runs four
96-core points at a time on 384 logical CPUs.  The shards are disjoint and
their union is the full 55-point campaign.

Both launchers first run `scripts/validate_13tev_corrected_campaign.py`.  This
fail-closed check requires the exact 55-point physics grid, independently
checks `D3=k3-1,D4=k4-1`, fixes `CT1=0`, checks the inactive contact is zero,
and verifies that the generated matrix element calls both the ordinary-SM and
anomalous `hhh/hhhh` couplings.  Every completed run is then checked again
against its stored MadGraph banner before its LHE is published.

After process generation, its runtime card templates can safely be normalized
to the all-SM point with:

```bash
python3 scripts/set_generated_process_sm_defaults.py \
  --process-dir "$PWD/MG5_aMC_v3_5_16/gg_hhh_restricted5"
```

This post-generation operation is distinct from the UFO restriction card:
keep the latter's nonzero illustrative `D3/D4` values while generating the
process so MadGraph does not remove the anomalous vertices.

On Tiresias:

```bash
cd /home/apapaefs/Projects/TripleHiggsTopEffects
scripts/run_13tev_corrected_tiresias.sh
```

On Odysseus:

```bash
cd /home/apapaefs/Projects/TripleHiggsTopEffects
scripts/run_13tev_corrected_odysseus.sh
```

Use `SMOKE_ONLY=1` to run only the convention pilot, `DRY_RUN=1` to inspect a
host's selected converted inputs, or `PREPARE_ONLY=1` to create its isolated
workers.  Set `SHARD_COUNT=1 SHARD_INDICES=0 EXPECTED_POINTS=55` only when a
single host should deliberately run the whole campaign.  The new outputs are
kept separate from the superseded samples:

```text
artifacts/lhe/13tev-kappa-corrected/
.work/13tev-kappa-corrected/
logs/13tev-kappa-corrected/
```

### Near-SM-rate `ct3` shape campaign and Figure 6-style plot

`scans/ct3.14tev-sm-shapes.csv` contains 12 HL-LHC points at the physical
self-coupling point `k3=k4=1`, spanning `ct3=-0.05` through `0.25` with
additional resolution around `ct3=0.18`.  This interval targets the rate
degeneracy where the inclusive cross section can remain close to the SM while
kinematic distributions change.  For every point the driver writes
`D3=D4=0`, as well as `CT1=CT2=0`; only `CT3` changes.

On Odysseus, generate 100,000 events per point with four 96-core jobs at a
time at 14 TeV using:

```bash
cd /home/apapaefs/Projects/TripleHiggsTopEffects
scripts/run_14tev_ct3_sm_shapes_odysseus.sh
```

The 14 TeV launcher attaches both its top-level controller and every isolated
MadGraph worker process group to Odysseus's installed thermal guard.  It reads
the guard's live controller marker from `/etc/ipmi-thermal-guard.conf` and
refuses to start if `ipmi-thermal-guard.timer` is not active.  This matters
because the parallel driver deliberately starts each point in a separate
process group; marking only the screen controller would not protect the four
active workers.

For a detached run, use:

```bash
cd /home/apapaefs/Projects/TripleHiggsTopEffects
screen -dmS hhh_ct3_shapes bash -lc \
  'scripts/run_14tev_ct3_sm_shapes_odysseus.sh > logs/14tev-ct3-sm-shapes-launcher.log 2>&1'
```

The guard checks every 15 seconds.  If it pauses the campaign, it does not
automatically send `SIGCONT`; after the machine has cooled, inspect and resume
all marked process groups with the installed guard's `status` and `resume`
commands.

Use `DRY_RUN=1` to print and validate all converted couplings without
launching MadGraph.  The dedicated outputs are written under
`artifacts/lhe/14tev-ct3-sm-shapes/`, with worker state and logs under the
matching `.work/` and `logs/` directories.  The default seeds are 36001
through 36012, disjoint from the earlier corrected campaign.

After all samples finish, the launcher automatically runs
`scripts/plot_ct3_shapes.py`.  It produces a Figure 6-style comparison in
which `k3=k4=1`, `CT1=CT2=0`, and only `CT3` varies.  The default curves are
the SM, `ct3=0.10`, and the near-rate-degenerate `ct3=0.18` point.  The two
panels contain normalized 40 GeV-bin distributions of `m3h` and the scalar
Higgs transverse-momentum sum.  The same observables are also written as
unnormalized absolute bin cross sections in pb per 40 GeV bin.  Both figures
omit `k3` and `k4` from curve labels when they equal one; a non-SM value is
included directly in that curve's legend entry.  Non-SM legend parameters are
ordered as `k3`, `k4`, then `kappa3t`.  Outputs are:

```text
artifacts/figures/14tev-ct3-sm-shapes.pdf
artifacts/figures/14tev-ct3-sm-shapes.png
artifacts/figures/14tev-ct3-sm-shapes-unnormalized.pdf
artifacts/figures/14tev-ct3-sm-shapes-unnormalized.png
artifacts/figures/14tev-ct3-sm-shapes.csv
```

To redraw a different set of completed points without regenerating events,
run, for example:

```bash
python3 scripts/plot_ct3_shapes.py \
  --ct3-values 0 0.05 0.18 0.25
```

For a comparison in which `k3` and `k4` also differ between curves, repeat
`--sample MANIFEST K3 K4 CT3`.  The first selection must be the SM reference.
The publication benchmarks are regenerated with the same setup as the rate
fit: PDF4LHC21_40 member 0 (LHAPDF ID 93100), MadGraph scale choice 4, and
`scalefact=0.5`, corresponding to `muR=muF=m3h/2`.  Launch the guarded
100,000-event production with:

```bash
screen -dmS hhh_ct3_pdf4_shapes bash -lc \
  'scripts/run_14tev_ct3_rate_matched_pdf4lhc21_odysseus.sh > logs/14tev-ct3-rate-matched-pdf4lhc21-launcher.log 2>&1'
```

The launcher plots the three completed samples automatically.  To reproduce
only that plotting step, run:

```bash
python3 scripts/plot_ct3_shapes.py \
  --sample artifacts/lhe/14tev-ct3-rate-matched-pdf4lhc21/manifest.jsonl 1 1 0 \
  --sample artifacts/lhe/14tev-ct3-rate-matched-pdf4lhc21/manifest.jsonl 2.10 17 -0.20 \
  --sample artifacts/lhe/14tev-ct3-rate-matched-pdf4lhc21/manifest.jsonl 1.9 0 0.40 \
  --expected-pdlabel lhapdf \
  --expected-lhaid 93100 \
  --expected-dynamical-scale-choice 4 \
  --expected-scalefact 0.5 \
  --expected-beam-energy-gev 7000 \
  --output artifacts/figures/14tev-ct3-rate-matched-benchmarks \
  --collider-label HL-LHC
```

This writes both normalized and absolute-bin-cross-section versions as
`14tev-ct3-rate-matched-benchmarks.{pdf,png}` and
`14tev-ct3-rate-matched-benchmarks-unnormalized.{pdf,png}`, together with a
CSV summary of the selected samples and their inclusive rates.  Plot ranges
are rounded from the largest weighted 99.5th percentile across the samples;
the accompanying `14tev-ct3-rate-matched-benchmarks-validation.json` records
the binning, common generation settings, plotted coverage, and normalized-to-
absolute histogram closure checks.

### Three-energy `kappa3t` rate parametrisation

The publication-rate campaign extends the Eq. 9 polynomial at 13, 13.6, and
14 TeV while fixing `CT1=CT2=0`.  With `x=k3-1`, `y=k4-1`, and `z=CT3`, the
exact LO basis is

```text
1, x, x^2, x^3, x^4, y, x*y, x^2*y, y^2,
z, x*z, x^2*z, y*z, z^2
```

The three tracked grids provide 15 zero-contact tensor points, 20 nonzero-CT3
anchor points, and six independent validation points per energy.  The launcher
uses PDF4LHC21_40 member 0 (LHAPDF ID 93100), MadGraph scale choice 4 with
`scalefact=0.5` to obtain `muR=muF=m3h/2`, four 96-core workers, and 20,000
events initially.  It stops after the zero-contact stage unless the SM rates
and Eq. 9 dependence pass the reproduction gate.  Points with an integration
error above 0.25% are automatically repeated with 100,000 events and
independent seeds.

Before the baseline grid, one 10-event SM smoke point at each energy verifies
the PDF, scale, generated process, and manifest uncertainty field.  Set
`SMOKE_ONLY=1` to stop after these three checks.

Run the complete guarded workflow on Odysseus with:

```bash
cd /home/apapaefs/Projects/TripleHiggsTopEffects
scripts/run_ct3_rate_fit_odysseus.sh
```

For a detached run:

```bash
screen -dmS hhh_ct3_rate_fit bash -lc \
  'scripts/run_ct3_rate_fit_odysseus.sh > logs/ct3-rate-fit-launcher.log 2>&1'
```

Use `DRY_RUN=1` to inspect all 123 initial fit and validation configurations
without creating workers.  Final outputs under `artifacts/fits/ct3-rate/`
include LaTeX equations, JSON and CSV coefficients, covariance and correlation
matrices, the Eq. 9 comparison, validation residuals, and PDF/PNG diagnostics.

After the fit has been produced, generate the Run-2/HL-LHC
`kappa3`--`kappa3t` and `kappa4`--`kappa3t` constraint plots with:

```bash
python3 scripts/plot_ct3_constraints.py
```

This reads `artifacts/fits/ct3-rate/coefficients.json` and writes PDF and PNG
versions of both two-panel figures, together with
`artifacts/figures/ct3-constraint-summary.json`.

On a host such as `physres1.kennesaw.edu`, where `lhapdf-config` is already in
`PATH` but the Tiresias Herwig module is unavailable, bypass the module load:

```bash
SKIP_MODULE=1 scripts/run_13tev_serial.sh
```

### Use all CPUs on `physres1`

The generated process has one subprocess and one integration channel.  A
single ordinary MadGraph run therefore does not fan out efficiently to all 64
hardware threads.  The parallel launcher makes one copy-on-write process clone
per scan point and runs the 24 independent points together.  With 64 CPU slots,
16 points receive three slots and eight receive two, exactly
`16*3 + 8*2 = 64`.  It also sets MadGraph's loop-induced
`survey_splitting` to the same per-point allocation, rather than accepting the
much smaller automatic square-root fan-out.

On `physres1.kennesaw.edu`, run the validated 100,000-event campaign with:

```bash
cd /home/apapaefs/Projects/TripleHiggsTopEffects
SKIP_MODULE=1 TOTAL_CORES=64 scripts/run_13tev_parallel.sh
```

The current machine exposes 64 hardware threads from 32 physical AMD EPYC
cores.  Here `TOTAL_CORES` means schedulable CPU slots, so 64 uses SMT as well.
The launcher refuses an allocation larger than its CPU affinity unless
`ALLOW_OVERSUBSCRIPTION=1` is deliberately supplied.

Worker processes live under `.work/13tev-parallel/processes/`.  On an XFS
filesystem, GNU `cp --reflink=auto` makes these clones space-efficient; the
portable fallback is a normal copy.  Each point writes a separate log under
`logs/13tev-parallel/`, avoiding interleaved MadGraph output.  Completed LHEs
and the combined manifest are published to `artifacts/lhe/13tev/`.

Inspect the exact 24-point allocation without creating workers or launching
MadGraph:

```bash
SKIP_MODULE=1 TOTAL_CORES=64 DRY_RUN=1 scripts/run_13tev_parallel.sh
```

Create or validate all isolated worker directories without generating events:

```bash
SKIP_MODULE=1 TOTAL_CORES=64 PREPARE_ONLY=1 scripts/run_13tev_parallel.sh
```

The parallel launcher assigns explicit, distinct seeds 13001 through 13024 so
that cloned processes do not inherit correlated automatic seed state.  It is
restartable: each worker validates and reuses a completed matching run.  If the
source generated process has intentionally changed, ensure no campaign is
running and use `REBUILD_WORKERS=1` once to replace only the generated worker
copies.

Common parallel-launcher overrides are:

| Environment variable | Default | Purpose |
|---|---:|---|
| `EVENTS` | `100000` | Events requested per point |
| `TOTAL_CORES` | online CPU count | Machine-wide CPU-slot budget |
| `EBEAM` | `6500` | Energy of each proton in GeV |
| `CT1` | `0` | Anomalous top-Yukawa shift `c_t1`; zero gives `kappa_t=1` |
| `CT2_POINTS` | `scans/ct2.13tev.csv` | `ct2` point grid |
| `CT3_POINTS` | `scans/ct3.13tev.csv` | `ct3` point grid |
| `SEED_START` | `13001` | First of the consecutive explicit point seeds |
| `OUTPUT_DIR` | `artifacts/lhe/13tev` | Published LHE and manifest directory |
| `WORK_DIR` | `.work/13tev-parallel` | Isolated process and task state |
| `LOG_DIR` | `logs/13tev-parallel` | Per-point logs |
| `MG5_ROOT` | `MG5_aMC_v3_5_16` | MadGraph installation |
| `PROCESS_DIR` | `$MG5_ROOT/gg_hhh_restricted5` | Source generated process |

For example, a 14 TeV, 20,000-event run on a 32-slot computer is:

```bash
SKIP_MODULE=1 EVENTS=20000 EBEAM=7000 TOTAL_CORES=32 \
  OUTPUT_DIR="$PWD/artifacts/lhe/my_14tev_scan" \
  WORK_DIR="$PWD/.work/my_14tev_scan" \
  scripts/run_13tev_parallel.sh
```

Use a distinct `OUTPUT_DIR`, `WORK_DIR`, point name, or all three when changing
physics settings.  A worker's resume validation includes the couplings, event
count, beam energy, seed, PDF, dynamical scale, systematics choice, and survey
splitting.

For a large campaign where each loop-induced point benefits from a substantial
MadGraph allocation, `run_parallel_scan.py --cores-per-point N` runs points in
waves.  For example, `--total-cores 192 --cores-per-point 96` runs two points
at a time and starts the next point whenever one completes.

The launchers obtain the LHAPDF data, library, and Python paths from
`lhapdf-config`.  Override the production event count with `EVENTS=N`; the
10-event pilot remains controlled separately by `SMOKE_EVENTS=N`.

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
