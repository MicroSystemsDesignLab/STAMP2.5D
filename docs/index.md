---
title: "STAMP-2.5D: Structural and Thermal Aware 2.5D Chiplet Floorplanning"
description: "Open-source ICCD 2025 reference implementation of the first floorplanner that jointly optimizes peak temperature, mechanical stress, and wirelength for 2.5D chiplet integration."
---

# STAMP-2.5D
### Structural and Thermal Aware Methodology for Placement in 2.5D Chiplet Integration

> Open-source reference implementation of the first automated 2.5D-chiplet floorplanner that **simultaneously** optimizes peak temperature, mechanical (von Mises) stress, and interconnect wirelength. Published at **ICCD 2025**.

[**GitHub repository →**](https://github.com/MicroSystemsDesignLab/STAMP2.5D) &nbsp; · &nbsp; [arXiv 2504.21140](https://arxiv.org/abs/2504.21140) &nbsp; · &nbsp; [IEEE Xplore](https://ieeexplore.ieee.org/document/11311107)

## What this is

STAMP-2.5D is an automated **thermal–mechanical co-optimization** framework for **chiplet placement** on 2.5D **silicon-interposer** packages. It closes a long-standing gap in prior **thermal-aware floorplanning** tools — TAP-2.5D, Floorplet, RLPlanner — by explicitly modeling **CTE-mismatch-driven thermo-elastic stress** and **self-weight-induced bending stress** alongside peak temperature.

The optimizer is a **B\*-tree + Fast Simulated Annealing** search whose cost function adaptively weights three normalized objectives. Each candidate placement is evaluated through **ANSYS coupled thermal–structural FEA** (~40k-element mesh) and a **MILP wirelength solver** adapted from TAP-2.5D.

## Headline results

Across three real chiplet architectures (Ascend910, Micro150, MultiGPU), STAMP-2.5D's full multi-physics objective (**WST**) reduces von Mises stress by **up to 19.8%** and total wirelength by **up to 19.3%**, with at most a 3% change in peak temperature, compared to conventional thermal-aware (WT) baselines:

| Architecture | Cost function | Peak temp (°C) | Peak σ<sub>vm</sub> (MPa) | Wirelength (mm) |
|---|---|---:|---:|---:|
| **Ascend910** | WT (T + WL) | 81.06 | 232.63 | 27 200 |
|   | WS (σ + WL) | 81.21 | 226.89 | 25 895 |
|   | **WST** | **79.04** | **222.14** | 27 787 |
| **MultiGPU**  | WT | 85.69 | 280.82 | 82 680 |
|   | WS | 87.07 | 275.85 | 98 794 |
|   | **WST** | 86.04 | **258.97** | **78 358** |
| **Micro150**  | WT | 95.24 | 291.02 | 104 314 |
|   | WS | 99.04 | 224.00 | 93 251 |
|   | **WST** | 98.07 | **233.47** | **84 227** |

The companion gradient analysis (paper §IV-B, Table III) shows that **temperature gradients**, not absolute temperatures, drive thermo-mechanical stress: gradient–stress correlations (−0.173 to −0.285) are 1.3×–11× stronger than temperature–stress correlations across all three architectures. That's the empirical justification for multi-physics co-optimization.

## Documentation

- [**Architecture**](ARCHITECTURE.md) — local ↔ remote setup, the SSH reverse tunnel, what runs where, why the split exists.
- [**Configuration**](CONFIGURATION.md) — every `<placeholder>` in the source code explained, with replacement values.
- [**Reproducing results**](REPRODUCING_RESULTS.md) — per-architecture commands that map directly to Tables II–IV of the paper.

## How it works

```
┌──────────────────────────────────────┐    SSH reverse tunnel    ┌──────────────────────────────────┐
│ REMOTE  (Linux compute server)       │                          │ LOCAL  (Windows + ANSYS license) │
│                                      │  -R 5000:localhost:8080  │                                  │
│  src/connector/thermal_connector.py  │ <───────────────────────│  src/architectures/<arch>/        │
│   • B*-tree representation           │                          │      server_temp_stress.py       │
│   • Fast Simulated Annealing         │                          │   • Flask, port 8080             │
│   • Cost = a·T + b·WL + c·σ          │  POST /execute_local_…  │   • Builds STEP geometry         │
│   • MILP wirelength solver           │ ───────────────────────▶│   • Runs ANSYS thermal+struct    │
│                                      │                          │   • Returns peak T, peak σ_vm    │
└──────────────────────────────────────┘                          └──────────────────────────────────┘
```

Why the split? ANSYS Mechanical desktop licenses run on Windows; SA + MILP optimization runs better on dedicated Linux compute. Treating FEA as an HTTP service decouples the two and leaves room to swap in a learned thermal surrogate later.

## Comparing with prior work

| Method | Year | Optimizes T | Optimizes σ<sub>vm</sub> | Optimizes WL | Code public |
|---|---|:-:|:-:|:-:|:-:|
| Floorplet (Chen et al.) | 2023 | ✓ | ✗ | ✓ | partial |
| Hong-Wen Chen et al. | 2023 | ✓ | ✗ | ✓ | ✗ |
| RLPlanner (Duan et al.) | 2023 | ✓ | ✗ | ✓ | ✗ |
| Zhi-Bing Deng et al. | 2024 | ✓ | ✗ | ✓ | ✗ |
| TAP-2.5D (Ma et al.) | 2021 | ✓ | ✗ | ✓ | [✓](https://github.com/bu-icsg/TAP-2.5D) |
| **STAMP-2.5D (this work)** | **2025** | **✓** | **✓** | **✓** | **✓** |

## Cite this work

```bibtex
@inproceedings{parekh2025stamp25d,
  author    = {Parekh, Varun Darshana and Hazenstab, Zachary Wyatt and
               Srinivasa, Srivatsa Rangachar and Chakrabarty, Krishnendu and
               Ni, Kai and Narayanan, Vijaykrishnan},
  title     = {{STAMP-2.5D}: Structural and Thermal Aware Methodology for
               Placement in 2.5D Integration},
  booktitle = {Proceedings of the IEEE International Conference on Computer Design (ICCD)},
  year      = {2025},
  doi       = {10.1109/ICCD.2025.11311107}
}
```

A machine-readable [`CITATION.cff`](https://github.com/MicroSystemsDesignLab/STAMP2.5D/blob/main/CITATION.cff) is included so GitHub renders a one-click "Cite this repository" box.

## Authors

Varun Darshana Parekh¹, Zachary Wyatt Hazenstab¹, Srivatsa Rangachar Srinivasa², Krishnendu Chakrabarty³, Kai Ni⁴, Vijaykrishnan Narayanan¹

¹ The Pennsylvania State University &nbsp; ² Intel &nbsp; ³ Arizona State University &nbsp; ⁴ University of Notre Dame

## Acknowledgements

> This material is based upon work supported by the **PRISM Center** under the **JUMP 2.0 Program** sponsored by **Semiconductor Research Corporation (SRC)**.

## License

[MIT](https://github.com/MicroSystemsDesignLab/STAMP2.5D/blob/main/LICENSE)

## Keywords

thermal-aware chiplet placement · 2.5D integration · silicon interposer · automated floorplanning · simulated annealing · B\*-tree · ANSYS · finite element analysis · CTE mismatch · von Mises stress · thermal-mechanical co-optimization · heterogeneous integration · advanced packaging · EDA · design automation · VLSI · ICCD 2025
