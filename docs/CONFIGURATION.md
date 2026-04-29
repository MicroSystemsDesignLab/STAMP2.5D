# Configuration

Every user-specific value in STAMP-2.5D's source files is marked with one of the placeholders below. Search-and-replace each one with your local equivalent before running.

A helper script (`scripts/parameterize.py`) is provided to *reverse* this — it strips lab-specific values out and re-installs the placeholders. It does **not** fill them in for you. The point is for the public repo to never contain anyone's personal paths or hostnames; you set them once on your own machine and never commit them back.

## Placeholders

| Placeholder | What it represents | Example value |
|---|---|---|
| `<path_to_your_workspace>` | Root directory on the **local Windows machine** where the ANSYS server reads geometry from and writes output XLS / CSV files. The .py files expect a sub-folder structure inside it (e.g. `AI_Temperature/Ascend910_july10/...`); you can keep that or change it as long as the references inside the same .py file stay consistent. | `C:\Users\alice\STAMP_workspace` |
| `<path_to_your_repo>` | Where you cloned this repository on the local Windows machine. Used to point the ANSYS scripts at `data/Final_Materials.xml`. | `C:\Users\alice\code\STAMP2.5D` |
| `<your_username>` | SSH username on the **remote** compute server (the box that runs the optimizer and the connector). Whatever your shell prompt shows after the `@`. | `alice` |
| `<your_remote_hostname>` | Fully-qualified hostname or IP of the remote compute server. | `compute01.lab.example.edu` |
| `<your_machine_id>` | Optional, only used in log banner strings. Replace with anything you find useful (host alias, room number, etc.) or just delete the surrounding string. | `lab-mac-01` |

## Files that need editing

After cloning, the following files contain placeholders you must replace before running:

| File | Placeholders inside |
|---|---|
| `src/architectures/ascend910/server_temp_stress.py` | `<path_to_your_workspace>`, `<path_to_your_repo>` |
| `src/architectures/ascend910/server_temponly.py`    | `<path_to_your_workspace>`, `<path_to_your_repo>` |
| `src/architectures/multigpu/server_temp_stress.py`  | `<path_to_your_workspace>`, `<path_to_your_repo>` |
| `src/architectures/multigpu/server_temponly.py`     | `<path_to_your_workspace>`, `<path_to_your_repo>` |
| `src/architectures/micro150/server_temp_stress.py`  | `<path_to_your_workspace>`, `<path_to_your_repo>` |
| `src/architectures/micro150/server_temponly.py`     | `<path_to_your_workspace>`, `<path_to_your_repo>` |
| `src/connector/thermal_connector.py` | None at present (target URL is `localhost:<TUNNEL_PORT>`) |

The notebooks under `notebooks/` may also contain leftover absolute paths from the original development environment — open each cell and adjust before running.

## Network layout

STAMP-2.5D uses an SSH reverse tunnel to bridge the remote optimizer and the local ANSYS server. Three port numbers must agree across three places:

| Setting | Default | Where it lives |
|---|---:|---|
| Local Flask port | `8080` | bottom of every `server_*.py` (`app.run(..., port=8080)`) |
| Tunnel remote port | `5000` | the `ssh -R 5000:localhost:8080 ...` command you launch from the local box |
| Connector target port | `5000` *(see note)* | `src/connector/thermal_connector.py` (`url = "http://localhost:5000/..."`) |

> **Known mismatch in the original code drop.** The connector ships with `localhost:5001` even though its own comment says "Use port 5000 since that's where the SSH tunnel is receiving." If you preserve the default `-R 5000:localhost:8080` tunnel command, change the URL in `thermal_connector.py` from `5001` to `5000`. Tracking as an open issue.

## ANSYS license

STAMP-2.5D requires ANSYS Mechanical 2024 R1 or newer on the local Windows machine. The simulation scripts use the [PyAnsys](https://docs.pyansys.com/) bindings (`ansys-mechanical-core`, `ansys-aedt-core`) which need a working desktop license to launch a `Mechanical` instance.

The repository **does not** ship any license keys, license-server addresses, or floating-license configuration. Configure `ANSYSLMD_LICENSE_FILE` (or your site equivalent) outside the repo — typically through your ANSYS installer.
