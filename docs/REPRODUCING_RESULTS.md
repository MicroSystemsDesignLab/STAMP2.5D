# Reproducing the paper's results

This document maps each row of Table II in the paper to a specific command in this repository.

## Headline experiments (Table II)

| Architecture | Cost function | Script | Interposer (mm) | h (W/m²·K) |
|---|---|---|---:|---:|
| Ascend910 | WT (Wirelength + Temperature) | `src/architectures/ascend910/server_temponly.py`    | 45 × 45 | 580 |
| Ascend910 | WS (Wirelength + Stress)      | *(reuse `server_temp_stress.py` with `a=0` weight)* | 45 × 45 | 580 |
| Ascend910 | **WST** (full multi-physics)  | `src/architectures/ascend910/server_temp_stress.py` | 45 × 45 | 580 |
| MultiGPU  | WT                            | `src/architectures/multigpu/server_temponly.py`     | 50 × 50 | 950 |
| MultiGPU  | WS                            | *(`server_temp_stress.py` with `a=0`)*              | 50 × 50 | 950 |
| MultiGPU  | **WST**                       | `src/architectures/multigpu/server_temp_stress.py`  | 50 × 50 | 950 |
| Micro150  | WT                            | `src/architectures/micro150/server_temponly.py`     | 50 × 50 | 720 |
| Micro150  | WS                            | *(`server_temp_stress.py` with `a=0`)*              | 50 × 50 | 720 |
| Micro150  | **WST**                       | `src/architectures/micro150/server_temp_stress.py`  | 50 × 50 | 720 |

The WS column is currently produced by setting the temperature weight `a` to zero in the WST script's adaptive cost function — we have not yet shipped a separate `server_stressonly.py`; tracked as a follow-up.

## Optimizer parameters (per the paper)

These are the SA parameters used for every entry in Table II:

| Parameter | Value |
|---|---:|
| Initial annealing temperature `T₀` | 1.0 |
| Cooling rate | 0.9 |
| Iterations per temperature level — Ascend910 | 45 |
| Iterations per temperature level — Micro150, MultiGPU | 50 |
| Convergence threshold | T ≤ 0.01 |
| Independent runs (statistical validation) | 5 |
| Mesh elements (medium) | ~40 000 |
| Ambient temperature | 23 °C |
| Substrate-bottom heat-transfer coefficient | 10 W/m²·K |

## Wall-clock budget

Per the paper:

- Single Ascend910 run: ~60.5 h
- Single Micro150 / MultiGPU run: ~67 h
- Full study (5 replicates × 3 architectures × 3 cost functions): ~300–335 h per architecture, ~900–1000 h total

Plan capacity accordingly. Cutting iteration counts and replicate counts trades reproducibility for speed.

## Section IV-B — Gradient–Stress correlation

To reproduce Table III (gradient analysis) and Figure 8 (gradient heat maps):

```bash
python src/analysis/gradient_analysis.py \
    --temp-files  results/paper_figures/<arch>/<...>_temp.xls \
    --stress-files results/paper_figures/<arch>/<...>_stress.xls \
    --out         results/gradient/<arch>/
```

Inputs are the per-cost-function temperature and stress XLS files exported by ANSYS during the headline runs. The script writes the gradient histograms, gradient-vector plots, and the Pearson correlation table.

## Section IV-C — Intra-chiplet power density study

The Vitruvian-on-Ascend910 sensitivity study (Table IV, Figs. 9–10) is set up under `sensitivity_study/`:

- `chiplet_power_map_from_new_table.csv` — coarse uniform-power map (baseline)
- `power_map_updated_0p5_singleZ.csv`     — fine-grained hotspot map for the Vitruvian die
- `intra_chiplet_variation.png`           — visualization of the two power maps
- `sensitivity_study.xlsx`                — paired peak-T and peak-σ_vm numbers under both power assumptions

This study holds the WT/WS/WST placements fixed and re-runs ANSYS with the alternative power maps, showing that the relative ranking of placements (WST best, then WT, then WS) is unchanged between the two power assumptions.

## Sanity-checking your setup

1. Run `python notebooks/installation.ipynb` end-to-end — it walks through the PyAnsys + license-detection sanity checks.
2. Run a 1-iteration optimizer cycle by setting `iterations_per_temp = 1` and `T_min = T₀ × 0.5` in the WST script you're testing. Should complete in ~15-25 min (one ANSYS round-trip), and should report a non-default `temp_current` and `stress_current`.
3. If you get the placeholder fallback values (`temp_current=1000, stress_current=2000`), the connector couldn't reach the Flask server — recheck the SSH tunnel and port numbers in `docs/CONFIGURATION.md`.
