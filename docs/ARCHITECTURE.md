# Architecture

STAMP-2.5D is split across two machines for one practical reason: ANSYS Mechanical desktop licenses are tied to a specific Windows host, while the optimizer benefits from running on dedicated compute. The split is also reflected in the file layout (`src/architectures/...` is local-side, `src/connector/...` is remote-side).

```
┌─────────────────────────────────────┐    SSH reverse tunnel    ┌──────────────────────────────────┐
│ REMOTE  (Linux compute server)      │                          │ LOCAL  (Windows + ANSYS)         │
│                                     │  -R 5000:localhost:8080  │                                  │
│  src/connector/thermal_connector.py │ <───────────────────────│  src/architectures/<arch>/        │
│   • B*-tree representation          │                          │      server_temp_stress.py       │
│   • Fast Simulated Annealing        │                          │   • Flask, port 8080             │
│   • Cost = a·T_norm + b·WL_norm     │  POST /execute_local_…  │   • POST handler builds STEP     │
│         + c·σ_norm                  │ ───────────────────────▶ │     geometry from layer file     │
│   • MILP wirelength solver          │                          │   • Calls ANSYS thermal+struct   │
│                                     │                          │   • Returns peak T, peak σ_vm    │
└─────────────────────────────────────┘                          └──────────────────────────────────┘
```

## Why the split?

- **ANSYS licensing.** Most academic ANSYS site licenses run as Windows desktop installs. They cannot be remoted-into for headless FEA without specific server-edition licensing.
- **Optimizer compute.** Simulated annealing on B\*-trees with full ANSYS-in-the-loop evaluation runs ~60 hours per architecture, per run, with five replicates. That's >300 wall-clock hours — comfortable on a remote compute box, painful on a development laptop.
- **Decoupling.** Treating the FEA evaluator as an HTTP service means the optimizer is unchanged whether you swap in a learned thermal surrogate later (we are working on this; see paper Section V "Future Work").

## What runs where

### Local Windows machine

- Listens on port `8080` for POST requests carrying a layer-stack description and a power density.
- For each request:
  1. Parses the layer file into chiplet geometry (`read_layers`, `geometry_from_layers`).
  2. Builds the STEP geometry of the package stack — substrate, C4 bumps, interposer, microbumps, chiplets, TIM, heatsink — using PyAEDT.
  3. Imports the STEP into ANSYS Mechanical, assigns materials from `data/Final_Materials.xml`, and runs steady-state coupled thermal–structural analysis.
  4. Reads peak temperature and peak von Mises stress out of the result XLS files.
  5. Returns `{ "temp_current": <peak_T>, "stress_current": <peak_sigma> }` to the caller.

### Remote Linux server

- Holds the optimizer logic and the SA loop.
- For each candidate placement, calls `thermal_mechanical_stress(layer_file, power_density)` which is a thin HTTP client to the local Flask service.
- Maintains the B\*-tree perturbations (jump, move, rotate), the cost function with adaptive weights `(a, b, c)`, and the Boltzmann acceptance criterion.
- Writes per-iteration logs and saves the best floorplan found.

## SSH reverse tunnel

The reverse tunnel is set up *from* the local Windows machine, *to* the remote server:

```bash
ssh -R 5000:localhost:8080 <your_username>@<your_remote_hostname>
```

This forwards port `5000` on the remote server to `localhost:8080` on the local Windows box. Once established, code on the remote server can reach the Flask endpoint at `http://localhost:5000/execute_local_function`. See [`CONFIGURATION.md`](CONFIGURATION.md) for the port-number gotcha (the connector currently hits `:5001`, which is a bug).

## Data flow

```
layer_file (txt) ──┐
                   │   POST /execute_local_function
                   ▼   ┌──────────────────────────────┐
optimizer  ────────▶  │  Flask (local Win + ANSYS)   │  ──▶  peak T, peak σ_vm
(remote)            │   └──────────────────────────────┘
                   ▲                                          │
                   │                                          ▼
                   └──── cost = a·T + b·WL + c·σ ──── update SA state
```

A "layer file" is a plain-text description of the package stack, with one line per layer (index, name, thickness in meters) followed by per-element lines (name, width, length, x-offset, y-offset). See `read_layers()` in any of the architecture servers for the exact format. Example layer files live under each architecture's results directory in the original development workspace; small demo layer files for the public quickstart will land in `data/examples/` in a follow-up release.

## Materials library

`data/Final_Materials.xml` is the ANSYS Engineering Data file used in every paper experiment. Each component in Table I of the paper (substrate, C4 bumps, microbumps, interposer, chiplets, TIM, heatsink, underfill) maps to a named material in this file. Material assignment happens in the `Material_Assignment_Script` block of each architecture's server.

## Known limitations

- **Wall-clock time.** A single architecture run is ~60–67 h; five replicates is ~300+ h.
- **Uniform per-chiplet power.** The default model assumes uniform power density inside a chiplet. The non-uniform / hotspot variant is implemented in the sensitivity study (see `sensitivity_study/`).
- **Single license required.** No headless / batch alternative is provided in this release.
- **Port mismatch in connector.** Tracked above and in `CONFIGURATION.md`.
