# Sensitivity study — intra-chiplet power-density variation

This directory contains the data and figures for **Section IV-C of the paper** (Table IV, Figures 9–10): the study of how non-uniform intra-chiplet power maps affect the placements that STAMP-2.5D produces.

## Question

The default STAMP-2.5D model assumes a uniform power density inside each chiplet. Real chiplets have hotspots — does that change the optimal placement?

## Setup

We took the final WT, WS, and WST placements that STAMP-2.5D produces for the Ascend910 architecture with the **Vitruvian** compute die, and re-ran ANSYS thermal–structural FEA on each placement under two power assumptions:

- **Uniform** — single average-power value per chiplet (`chiplet_power_map_from_new_table.csv`).
- **Non-uniform** — block-level hotspot map for the Vitruvian die (`power_map_updated_0p5_singleZ.csv`, derived from Liao et al., *DaVinci: A Scalable Architecture for Neural Network Computing*, HotChips 2019).

## Files

| File | What it is |
|---|---|
| `chiplet_power_map_from_new_table.csv`  | Uniform-power baseline map |
| `power_map_updated_0p5_singleZ.csv`     | Fine-grained hotspot map for the Vitruvian die |
| `intra_chiplet_variation.png`           | Side-by-side visualization of the two maps |
| `sensitivity_study.xlsx`                | Paired peak-T / peak-σ_vm under both power assumptions |

## Headline finding

The relative ranking of placements is **stable** under both power assumptions — WST produces the lowest peak temperature and the lowest peak σ<sub>vm</sub>, followed by WT, then WS — for both uniform and hotspot inputs. Absolute values shift by under 2% between the two cases.

This means a simple uniform-power model is good enough for early-stage thermal–mechanical floorplanning. The hotspot map only matters for the final sign-off simulation, not for the optimizer's inner loop. That's a useful design-time speedup.

## Reproducing

These figures and numbers were generated in ANSYS Mechanical against the placements optimized in the headline experiments. Re-running them requires the per-placement `.mechdb` project files, which are too large for git and are kept on the development workstation. They will be uploaded to Zenodo as part of the v1.0 data release (DOI to follow); see [`docs/REPRODUCING_RESULTS.md`](../docs/REPRODUCING_RESULTS.md) for the recipe once available.
