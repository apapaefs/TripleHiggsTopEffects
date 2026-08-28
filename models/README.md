# Vendored restricted loop model

`heft_loop_sm_restricted5/` is the UFO used by this repository to generate
loop-induced Higgs-pair and triple-Higgs matrix elements with the five
anomalous inputs `D3`, `D4`, `CT1`, `CT2`, and `CT3`.

The model contains ordinary SM `hhh` and `hhhh` vertices as well as additional
vertices proportional to `D3` and `D4`.  Thus `D3` and `D4` are shifts:
`k3=1+D3` and `k4=1+D4`; the SM point is `D3=D4=0`.  The campaign CSVs store
the kappas, and `scripts/run_scan.py` subtracts one before writing LHA codes
996 and 997.  The nonzero illustrative values retained in the UFO restriction
card are not campaign defaults: MadGraph uses restriction values while
constructing a process, and zeroing an input there can remove the associated
anomalous vertex.  The campaign driver overwrites all five runtime card inputs.

## Provenance

The files were exported from:

```text
git@gitlab.com:apapaefs/multihiggs_loop_sm.git
commit 99ba5ee9066943a727f063099053604ea2e2f102
```

The export retains the UFO Python source and restriction cards.  The sole
campaign-specific default change is that `CT1` is initialized to zero in both
`parameters.py` and `restrict_default.dat`: this is the SM top-Yukawa baseline
because the model uses `kappa_t = 1 + CT1`.  The upstream snapshot's
illustrative value was 1.3; no interaction or counterterm expression was
changed.  macOS AppleDouble files (`._*`) and editor swap files (`*.swp`) from
the source checkout were excluded because they are not model inputs.

## Reference

Andreas Papaefstathiou and Gilberto Tetlalmatzi-Xolocotzi,
“Multi-Higgs boson production with anomalous interactions at current and
future proton colliders,” JHEP 06 (2024) 124,
[arXiv:2312.13562](https://arxiv.org/abs/2312.13562).

For the restricted model, triple-Higgs production is generated with:

```text
generate g g > h h h [noborn=QCD MHEFT] MHEFT^2<=6
```

`scripts/prepare_process.py` copies this directory into a MadGraph
installation by default.  Use `--model-source` only to select a different UFO
snapshot deliberately.

To copy only the UFO by hand from the repository root, use:

```bash
cp -a models/heft_loop_sm_restricted5 /path/to/MG5_aMC_v3_5_16/models/
```
