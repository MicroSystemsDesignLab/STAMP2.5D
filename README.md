# STAMP-2.5D
### Structural and Thermal Aware Methodology for Placement in 2.5D Chiplet Integration

[![Paper](https://img.shields.io/badge/paper-ICCD%202025-blue)](https://ieeexplore.ieee.org/document/11311107)
[![arXiv](https://img.shields.io/badge/arXiv-2504.21140-b31b1b)](https://arxiv.org/abs/2504.21140)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![ANSYS](https://img.shields.io/badge/ansys-2024%20R1%2B-orange)](https://www.ansys.com/)

> Open-source reference implementation of the first automated 2.5D-chiplet floorplanner that **simultaneously** optimizes peak temperature, mechanical (von Mises) stress, and interconnect wirelength. Published at **ICCD 2025**.

## TL;DR

STAMP-2.5D is an automated **thermal–mechanical co-optimization** framework for **chiplet placement** on 2.5D **silicon-interposer** packages. It closes a long-standing gap in prior **thermal-aware floorplanning** tools (TAP-2.5D, Floorplet, RLPlanner) by explicitly modeling **CTE-mismatch-driven thermo-elastic stress** and **self-weight-induced bending stress** alongside peak temperature.

Across three real chiplet architectures — **Ascend910**, **Micro150**, and **MultiGPU** — STAMP-2.5D reduces von Mises stress by **up to 19.8%** and total wirelength by **up to 19.3%** with at most a 3% change in peak temperature, compared to temperature-only baselines.

## Why this exists

Conventional 2.5D floorplanning packs chiplets tightly to minimize wirelength, which creates thermal hotspots and amplifies coefficient-of-thermal-expansion (CTE) mismatch between heterogeneous dies and the silicon interposer. Prior thermal-aware methods (TAP-2.5D, Floorplet, Hong-Wen Chen et al., RLPlanner) optimize temperature and wirelength but ignore mechanical stress — yet stress is the dominant reliability failure mode in 2.5D packages (interposer warpage, solder-joint cracking, microbump fatigue). STAMP-2.5D is the first automated tool to co-optimize all three.

Under the hood it couples a **B\*-tree + Fast Simulated Annealing** search with **ANSYS coupled thermal–structural finite element analysis** (FEA) and a **MILP wirelength solver** adapted from TAP-2.5D.

## Headline results (Table II of the paper)

| Architecture | Cost function | Peak temp (°C) | Peak σ<sub>vm</sub> (MPa) | Wirelength (mm) |
|---|---|---:|---:|---:|
| **Ascend910** | WT (T + WL) | 81.06 | 232.63 | 27 200 |
|   | WS (σ + WL) | 81.21 | 226.89 | 25 895 |
|   | **WST (T + σ + WL)** | **79.04** | **222.14** | 27 787 |
| **MultiGPU** | WT | 85.69 | 280.82 | 82 680 |
|   | WS | 87.07 | 275.85 | 98 794 |
|   | **WST** | 86.04 | **258.97** | **78 358** |
| **Micro150** | WT | 95.24 | 291.02 | 104 314 |
|   | WS | 99.04 | 224.00 | 93 251 |
|   | **WST** | 98.07 | **233.47** | **84 227** |

**WT** = Wirelength + Temperature (conventional thermal-aware baseline).
**WS** = Wirelength + Stress (mechanical-only baseline).
**WST** = Wirelength + Stress + Temperature (full STAMP-2.5D objective).

The companion gradient analysis (Section IV-B of the paper, Table III) shows that **temperature gradients**, not absolute temperatures, drive thermo-mechanical stress: gradient-vs-stress correlations (−0.173 to −0.285) are 1.3×–11× stronger than temperature-vs-stress correlations across all three architectures. This is what justifies multi-physics co-optimization over thermal-only optimization.

## Repository layout

```
.
├── src/
│   ├── architectures/
│   │   ├── ascend910/        # Huawei Ascend 910 (45 mm interposer, 580 W/m²·K)
│   │   ├── multigpu/         # Multi-GPU package (50 mm interposer, 950 W/m²·K)
│   │   └── micro150/         # Micro150 disintegrated CPU (50 mm interposer, 720 W/m²·K)
│   │      └── server_temp_stress.py   # WST objective (full multi-physics)
│   │      └── server_temponly.py      # WT  objective (thermal-only baseline)
│   ├── connector/
│   │   └── thermal_connector.py       # Remote-side client; POSTs power maps over SSH tunnel
│   └── analysis/
│       └── gradient_analysis.py       # Reproduces Section IV-B (gradient–stress correlation)
├── data/
│   └── Final_Materials.xml            # ANSYS engineering-data library used in all simulations
├── notebooks/
│   ├── geometry_generation.ipynb      # Builds the 2.5D stack STEP geometry
│   └── installation.ipynb             # Environment setup walkthrough
├── results/
│   └── paper_figures/                 # Figures + per-arch metrics CSVs from the paper
├── sensitivity_study/                 # Section IV-C: intra-chiplet power-density study
├── docs/
│   ├── ARCHITECTURE.md                # Local ↔ remote tunnel setup
│   ├── CONFIGURATION.md               # All `<placeholder>` values explained
│   └── REPRODUCING_RESULTS.md         # Per-architecture how-to
├── scripts/
│   └── parameterize.py                # Idempotent placeholder substitution helper
├── CITATION.cff
├── LICENSE                            # MIT
├── requirements.txt
└── README.md
```

## How it works

STAMP-2.5D runs as a **client–server pair**. The optimizer (Simulated Annealing on a B\*-tree representation) lives on a remote Linux server; ANSYS Mechanical lives on a local Windows workstation under a desktop license. They talk over an SSH reverse tunnel.

```
┌──────────────────────────────────┐         SSH reverse tunnel         ┌──────────────────────────────────┐
│ REMOTE  (Linux compute server)   │  -R <TUNNEL_PORT>:localhost:<...> │ LOCAL  (Windows + ANSYS license) │
│                                  │  ──────────────────────────────▶  │                                  │
│  thermal_connector.py            │                                    │  server_temp_stress.py (Flask)   │
│   • B*-tree + Fast SA            │   POST /execute_local_function     │   • Builds STEP geometry         │
│   • Cost = a·T + b·WL + c·σ      │   { layer_file, power_density }    │   • Runs ANSYS thermal+struct FEA│
│   • MILP wirelength solver       │ ──────────────────────────────▶    │   • Returns peak T, peak σ_vm    │
└──────────────────────────────────┘                                    └──────────────────────────────────┘
```

This split is the only practical way to run inside a typical academic ANSYS site license (Windows-only desktop license + remote compute resources). Documented in detail in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Quickstart

> **Heads up.** STAMP-2.5D requires an **ANSYS Mechanical 2024 R1+** license on the local Windows machine. There is no purely-open-source path to FEA results — this is a research artifact reproducing a specific paper, not a license-free EDA tool. Without ANSYS you can still inspect every source file, the gradient analysis, the materials library, and the published figures.

### 1. Clone and install Python dependencies

```bash
git clone https://github.com/MicroSystemsDesignLab/STAMP2.5D.git
cd STAMP2.5D
pip install -r requirements.txt
```

### 2. Configure your paths

Open the architecture you want to run, e.g. `src/architectures/ascend910/server_temp_stress.py`, and replace every placeholder of the form `<path_to_your_*>` and `<your_*>` with your local values. See [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) for the complete list and what each one means.

### 3. Set up the SSH tunnel and run the local Flask server

On the local Windows box (the one with ANSYS):

```powershell
python src\architectures\ascend910\server_temp_stress.py
# Flask now listens on port 8080
```

On the remote compute server:

```bash
ssh -R 5000:localhost:8080 <your_username>@<your_remote_hostname>
# Then in another shell on the remote box:
python src/connector/thermal_connector.py
```

### 4. Reproduce a paper result

See [`docs/REPRODUCING_RESULTS.md`](docs/REPRODUCING_RESULTS.md) for the per-architecture command, expected runtime, and how each entry in the headline-results table maps to a specific config.

## Comparing with prior work

| Method | Year | Optimizes T | Optimizes σ<sub>vm</sub> | Optimizes WL | Code public |
|---|---|:-:|:-:|:-:|:-:|
| Floorplet (Chen et al.) | 2023 | ✓ | ✗ | ✓ | partial |
| Hong-Wen Chen et al. | 2023 | ✓ | ✗ | ✓ | ✗ |
| RLPlanner (Duan et al.) | 2023 | ✓ | ✗ | ✓ | ✗ |
| Zhi-Bing Deng et al. | 2024 | ✓ | ✗ | ✓ | ✗ |
| TAP-2.5D (Ma et al.) | 2021 | ✓ | ✗ | ✓ | [✓](https://github.com/bu-icsg/TAP-2.5D) |
| **STAMP-2.5D (this work)** | **2025** | **✓** | **✓** | **✓** | **✓ (this repo)** |

## Citing STAMP-2.5D

If you use STAMP-2.5D in your research, please cite:

```bibtex
@inproceedings{parekh2025stamp25d,
  author    = {Parekh, Varun Darshana and Hazenstab, Zachary Wyatt and
               Srinivasa, Srivatsa Rangachar and Chakrabarty, Krishnendu and
               Ni, Kai and Narayanan, Vijaykrishnan},
  title     = {{STAMP-2.5D}: Structural and Thermal Aware Methodology for
               Placement in 2.5D Integration},
  booktitle = {Proceedings of the IEEE International Conference on
               Computer Design (ICCD)},
  year      = {2025},
  doi       = {10.1109/ICCD.2025.11311107}
}
```

A machine-readable [`CITATION.cff`](CITATION.cff) is provided so GitHub renders a one-click "Cite this repository" box.

## Authors

- **Varun Darshana Parekh**¹ — [parekhvarun.com](https://www.parekhvarun.com/)
- **Zachary Wyatt Hazenstab**¹
- **Srivatsa Rangachar Srinivasa**²
- **Krishnendu Chakrabarty**³
- **Kai Ni**⁴
- **Vijaykrishnan Narayanan**¹

¹ The Pennsylvania State University ² Intel ³ Arizona State University ⁴ University of Notre Dame

## Acknowledgements

> This material is based upon work supported by the **PRISM Center** under the **JUMP 2.0 Program** sponsored by **Semiconductor Research Corporation (SRC)**.

We gratefully acknowledge SRC and the PRISM Center for their support of this research, and the [Microsystems Design Lab at Penn State](https://sites.psu.edu/microsystemsdesignlab/) for hosting the work.

## License

MIT — see [`LICENSE`](LICENSE).

## Keywords

thermal-aware chiplet placement · 2.5D integration · silicon interposer · automated floorplanning · simulated annealing · B\*-tree · ANSYS · finite element analysis · CTE mismatch · von Mises stress · thermal-mechanical co-optimization · heterogeneous integration · advanced packaging · EDA · design automation · VLSI · ICCD 2025
