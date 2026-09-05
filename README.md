# RISC-V PMP Physical Memory Agent

> **Domain:** Hardware Security & Physical Memory Protection  
> **Standard:** RISC-V Privileged Architecture v1.12

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB.svg?logo=python&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-46%20Passed-brightgreen.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white)

</div>

---

## 📖 What It Does

RISC-V PMP (Physical Memory Protection) Simulator and Security Analysis Agent. This project provides:

1. **PMP Simulator** (`simulator.py`): A faithful implementation of RISC-V PMP address matching and access control logic, supporting TOR, NA4, and NAPOT modes.
2. **Security Analysis Agent** (`agents/`): Multi-worker analysis system with PHI outbound protection and HMAC-SHA256 tamper-evident audit trails.
3. **RISC-V PMP Agent** (`riscv_pmp_agent/`): Distributed component coordination with sub-agents for address decoding, range validation, and configuration verification.
4. **Enrichment Suite** (`enrichment.py`): Domain-specific analysis engines for PMP compliance, attack detection, and secure boot verification.

---

## ⚙️ Key Capabilities

- **PMP Address Matching**: TOR (Top of Range), NA4 (Naturally Aligned 4-byte), NAPOT (Naturally Aligned Power-of-Two)
- **Access Control**: R/W/X permissions with privilege mode checking (U/S/M)
- **Lock Bit Support**: Prevents modification even from M-mode
- **PHI Outbound Guard**: Regex-based detection and blocking of protected health information
- **HMAC-SHA256 Audit Trail**: Cryptographically chained, tamper-evident logging
- **Multi-Worker Analysis**: Invariant QC, Safety Escalation, Protocol Conformance workers
- **FastAPI REST API**: Health, metrics, audit, and chat endpoints
- **Prometheus Telemetry**: Operational metrics export

---

## 💻 Installation

```bash
# Clone the repository
git clone https://github.com/abusuraihsakhri/riscv-pmp-physical-memory-agent.git
cd riscv-pmp-physical-memory-agent

# Install dependencies
pip install fastapi uvicorn pydantic pytest
```

---

## 🚀 CLI Usage

### PMP Simulator CLI (`cli.py`)

```bash
# Check a memory access against PMP rules
python cli.py check --address 0x1000 --access rw --privilege M --setup

# Configure a PMP entry
python cli.py configure --entry 0 --address 0x1000 --size 0x40 --access rwx --mode napot

# Show the current PMP memory map
python cli.py map --setup

# Run a full simulation with standard protection
python cli.py simulate

# Show full PMP state
python cli.py status --setup

# Set up standard protection
python cli.py setup
```

### RISC-V PMP Agent CLI (`riscv_pmp_agent/cli.py`)

```bash
# Run a single task evaluation
python riscv_pmp_agent_app.py audit --task-id TASK-001 --primary 29.4 --secondary 15.1

# System configuration query
python riscv_pmp_agent_app.py chat "What is the system status?"

# Batch process CSV records
python riscv_pmp_agent_app.py batch -i sample.csv -o results.csv

# Launch FastAPI REST server
python riscv_pmp_agent_app.py serve --host 127.0.0.1 --port 8000

# Verify HMAC-SHA256 audit trail integrity
python riscv_pmp_agent_app.py verify-audit
```

---

## 🧪 Testing

```bash
# Run all tests
pytest -v

# Run specific test suites
pytest tests/test_simulator.py -v      # PMP simulator core tests (38 tests)
pytest tests/test_riscv_pmp_agent.py -v # RISC-V PMP agent tests (3 tests)
pytest tests/test_enrichment.py -v      # Enrichment suite tests (2 tests)
```

---

## 🐳 Docker Deployment

```bash
# Build and run with Docker
docker build -t riscv-pmp-physical-memory-agent .
docker run -p 8000:8000 -e AUDIT_SECRET_KEY=your-secret-key riscv-pmp-physical-memory-agent

# Or use docker-compose
docker-compose up
```

---

## 🔒 Security

- **Audit Secret Key**: Set `AUDIT_SECRET_KEY` environment variable in production. A warning is issued if not set.
- **PHI Protection**: Active regex inspection blocks SSNs, MRNs, phone numbers, and patient identifiers.
- **Input Validation**: All PMP configuration and access check inputs are validated.

---

## 📁 Project Structure

```
riscv-pmp-physical-memory-agent/
├── cli.py                      # PMP Simulator CLI
├── simulator.py                # Core PMP simulation engine
├── riscv_pmp_agent_app.py      # RISC-V PMP Agent entry point
├── enrichment.py               # Domain-specific enrichment engines
├── agents/                     # Security analysis agents
│   ├── base.py                 # PHI guard, audit trail, security
│   ├── models.py               # Pydantic data models
│   ├── workers.py              # Specialized analysis workers
│   ├── supervisor.py           # Multi-agent orchestrator
│   ├── api.py                  # FastAPI REST endpoints
│   ├── llm_factory.py          # LLM provider abstraction
│   ├── learning.py             # Bayesian calibration engine
│   ├── metrics.py              # Prometheus metrics collector
│   └── streamer.py             # WebSocket telemetry broadcaster
├── riscv_pmp_agent/            # RISC-V PMP coordination agent
│   ├── models.py               # Data models
│   ├── engine.py               # Core algorithmic engine
│   ├── agents.py               # Sub-agents and coordinator
│   ├── cli.py                  # Agent CLI
│   └── server.py               # FastAPI server factory
├── tests/                      # Test suite
│   ├── test_simulator.py       # PMP simulator tests
│   ├── test_riscv_pmp_agent.py # Agent tests
│   ├── test_enrichment.py      # Enrichment tests
│   └── test_riscv_pmp_physical_memory_agent.py # Integration tests
├── web/                        # Web operations console
├── Dockerfile                  # Docker build config
├── docker-compose.yml          # Docker Compose config
└── pyproject.toml              # Project metadata
```

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.
