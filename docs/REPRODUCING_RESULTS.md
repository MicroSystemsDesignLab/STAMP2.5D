[← Back to STAMP-2.5D home](index.md)

# Reproducing the paper's results

This document maps each row of Table II in the paper to a specific command in this repository. The optimizer lives in `src/optimizer/`; the per-architecture configs live in `configs/`.

## Headline experiments (Table II)

| Architecture | Cost function | Config file | Interposer (mm) | h (W/m²·K) |
|---|---|---|---:|---:|
| Ascend910 | WT (Wirelength + Temperature)         | `configs/sys_ascend910.cfg`           | 45 × 45 | 580 |
| Ascend910 | WS (Wirelength + Stress)              | `configs/sys_ascend910_wl_stress.cfg` *(set `cost_mode = ws` inside)*   | 45 × 45 | 580 |
| Ascend910 | **WST** (Wirelength + Stress + Temp)  | `configs/sys_ascend910_wl_stress.cfg` *(default `cost_mode = wst`)*     | 45 × 45 | 580 |
| MultiGPU  | WT                                    | `configs/sys_multigpu.cfg`            | 50 × 50 | 950 |
| MultiGPU  | WS                                    | `configs/sys_multigpu_wl_stress.cfg`  *(`cost_mode = ws`)*              | 50 × 50 | 950 |
| MultiGPU  | **WST**                               | `configs/sys_multigpu_wl_stress.cfg`                                    | 50 × 50 | 950 |
| Micro150  | WT                                    | `configs/sys_micro150.cfg`            | 50 × 50 | 720 |
| Micro150  | WS                                    | `configs/sys_micro150_wl_stress.cfg`  *(`cost_mode = ws`)*              | 50 × 50 | 720 |
| Micro150  | **WST**                               | `configs/sys_micro150_wl_stress.cfg`                                    | 50 × 50 | 720 |

The `_wl_stress.cfg` configs are the multi-physics ones; switching between WS and WST is a config-internal flag. The plain `.cfg` files are the temperature-only baselines.

## End-to-end run

A full STAMP-2.5D run requires **both halves of the system** simultaneously:

1. **Local Windows machine** (with ANSYS Mechanical 2024 R1+):

   ```powershell
   python src\architectures\ascend910\server_temp_stress.py
   ```

   The Flask service listens on `localhost:8080` for thermal-mechanical evaluation requests.

2. **Remote compute server** (with the SSH reverse tunnel established to the local box):

   ```bash
   # In one terminal — start the tunnel
   ssh -R 5000:localhost:8080 <your_username>@<your_remote_hostname>

   # In another terminal on the same remote box — run the optimizer
   cd ~/STAMP2.5D
   python src/optimizer/sim_annealing.py configs/sys_ascend910_wl_stress.cfg
   ```

   The optimizer runs the SA loop, calls `thermal_connector.py` per iteration, which POSTs to the local Flask server, which in turn drives ANSYS and returns peak T + peak σ_vm. The connector's HTTP target must match the SSH tunnel; see [`CONFIGURATION.md`](CONFIGURATION.md) for the port-number gotcha.

3. **Outputs.** The optimizer writes per-iteration logs and the best floorplan found into the `path` directory specified in the config. The local server writes ANSYS exports (`*_temp.xls`, `*_stress.xls`) into the architecture's working directory.

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

These live in the `[general]` and `[fastSA]` sections of each `configs/sys_*.cfg`.

## Wall-clock budget

Per the paper:

- Single Ascend910 run: ~60.5 h
- Single Micro150 / MultiGPU run: ~67 h
- Full study (5 replicates × 3 architectures × 3 cost functions): ~300–335 h per architecture, ~900–1000 h total

Plan capacity accordingly. Cutting iteration counts and replicate counts trades reproducibility for speed.

## Section IV-B — Gradient–stress correlation

To reproduce Table III (gradient analysis) and Figure 8 (gradient heat maps):

```bash
python src/analysis/gradient_analysis.py \
    --temp-files   results/paper_figures/<arch>/<...>_temp.xls \
    --stress-files results/paper_figures/<arch>/<...>_stress.xls \
    --out          results/gradient/<arch>/
```

Inputs are the per-cost-function temperature and stress XLS files exported by ANSYS during the headline runs. The script writes the gradient histograms, gradient-vector plots, and the Pearson correlation table.

## Section IV-C — Intra-chiplet power-density study

The Vitruvian-on-Ascend910 sensitivity study (Table IV, Figs. 9–10) is set up under `sensitivity_study/`. See [`sensitivity_study/README.md`](../sensitivity_study/README.md) for the exact recipe.

## Sanity-checking your setup

1. Run `python notebooks/installation.ipynb` end-to-end — it walks through the PyAnsys + license-detection sanity checks.
2. Run a 1-iteration optimizer cycle by lowering `iterations_per_temp` and `T_min` in your chosen `configs/sys_*.cfg`. Should complete in ~15–25 min (one ANSYS round-trip), and should report a non-default `temp_current` and `stress_current`.
3. If the optimizer's log shows the placeholder fallback values (`temp_current=1000, stress_current=2000`), the connector couldn't reach the Flask server — recheck the SSH tunnel and port numbers in [`CONFIGURATION.md`](CONFIGURATION.md).
