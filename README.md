# RISC-V PMP Physical Memory Agent

### [Open the Browser Inspector →](https://abusuraihsakhri.github.io/riscv-pmp-physical-memory-agent/)

Model baseline RISC-V physical memory protection (PMP) permissions and region matching, using a Python CLI or a static, entirely local browser interface. This repository also contains separate heuristic telemetry/audit components; their threshold alerts are **not** PMP architecture conformance tests.

## What it supports

- **Python simulator** (`simulator.py`): priority-ordered TOR, NA4 and NAPOT regions, R/W/X permissions, M/S/U privilege checks, locked configurations and full-memory-operation boundary checks.
- **Browser inspector** (`web/`): edit PMP entries, test an access, inspect the encoded address registers and export a JSON report without a server or third-party dependencies.
- **CLI** (`cli.py`): inspect a sample memory map, simulate accesses, configure example regions and check permissions.
- **Optional agent API** (`riscv_pmp_agent/`): independent numeric-threshold demonstrations with `/health`, `/api/audit` and `/api/chat`. These endpoints do **not** run the PMP simulator.
- **Audit subsystem** (`agents/`): in-memory HMAC-SHA256 chain and heuristic identifier filtering, with a separate API.

## Browser use

Open the Pages link above, or open `web/index.html` locally. Start with the supplied ROM/RAM/MMIO/Flash example, then configure an entry by index and addressing mode. NAPOT takes a naturally aligned base and power-of-two size (8 bytes or greater); NA4 uses a 4-byte base; TOR uses the *top address* and the preceding entry's `pmpaddr` register as the lower bound, even if that entry is OFF. Test an R/W/X operation by privilege, address and size. Locked configurations cannot be changed through the form without resetting the simulator.

All calculations and JSON exports execute locally in your browser. Nothing is uploaded, saved on a server or persisted across page reloads.

## Python CLI and tests

Requires Python 3.9 or newer.

```bash
git clone https://github.com/abusuraihsakhri/riscv-pmp-physical-memory-agent.git
cd riscv-pmp-physical-memory-agent
python -m pip install -e ".[api,test]"
python cli.py simulate
python cli.py check --address 0x1000 --access r --privilege U --setup
python -m pytest -q
node --test tests/pmp_web.test.cjs  # optional: browser engine tests (Node 22)
```

The standalone simulator uses Python's standard library. The optional agent module can be run with:

```bash
riscv-pmp-physical-memory-agent audit --task-id DEMO --primary 12 --secondary 4 --status NOMINAL
riscv-pmp-physical-memory-agent batch -i sample.csv -o results.csv
riscv-pmp-physical-memory-agent serve --host 127.0.0.1 --port 8000
```

`batch` accepts the boolean flags `true/false`, `yes/no`, or `1/0` in its CSV column.

## Container

```bash
export AUDIT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
docker compose up --build
```

The Compose service binds to `127.0.0.1:8000` by default. It serves the *optional numeric-threshold agent API*, not the standalone browser application or PMP simulator. Keep the signing key secret and out of version control.

## Scope and security limitations

This is a **baseline PMP educational software model**, not a hardware verification tool or a guarantee of platform isolation. It does not implement Smepmp/ePMP policy changes, virtual memory, configurable PMP grain or implementation-specific behavior. `check_access` treats the provided byte range as one memory operation; hardware may split misaligned memory operations. It models 16 entries by default.

The heuristic agent subsystem performs ordinary rule-based threshold classification, not formal standards validation. Its regex-based identifier guard is **not sufficient to establish HIPAA compliance**. The audit chain is ephemeral and HMAC-checked, but does not provide tamper-proof external storage or authenticated network access. Do not expose the example APIs to untrusted networks without adding authentication, TLS and operational protections.

## Development and compatibility

- Pure Python simulation; FastAPI/Pydantic are optional for agent APIs.
- Static HTML, CSS and modern JavaScript with native `BigInt`; current Chrome, Firefox, Safari and Edge.
- CI covers Python 3.9–3.13, JavaScript regression tests, and package wheel generation.
- No browser Python runtime is required; the browser inspector implements the same basic PMP concepts directly in JavaScript.

Reference: [RISC-V Privileged Architecture specification](https://docs.riscv.org/reference/isa/priv/machine.html).

## License

[MIT](LICENSE).
