# RISC-V PMP (Physical Memory Protection) Simulator

A Python simulator for RISC-V Physical Memory Protection. Implements PMP register management, address matching (TOR, NA4, NAPOT), access permission checking, priority resolution, and lock bit enforcement per the RISC-V Privileged Specification.

## What This Actually Does

This is a **simulation** of the RISC-V PMP unit. It faithfully implements the address matching algorithms, permission checking logic, priority resolution (entry 0 = highest), and lock bit behavior defined in the RISC-V Privileged Architecture specification.

## PMP Features Implemented

### Address Matching Modes
- **OFF**: Entry disabled
- **TOR** (Top of Range): Address range from previous entry's top to this entry's top
- **NA4**: Naturally aligned 4-byte region
- **NAPOT**: Naturally aligned power-of-two region (8 bytes to 2^56 bytes)

### Access Permissions
- **R** (Read): Data read access
- **W** (Write): Data write access
- **X** (Execute): Instruction fetch access

### Priority
- PMP entry 0 has the **highest** priority
- First matching entry determines access
- If no entry matches: M-mode allows, S/U-mode denies

### Lock Bit
- **L=1**: Entry cannot be modified even from M-mode
- Locked entries persist across context switches
- Only way to unlock: system reset

## Quick Start

```bash
# Run full simulation
python cli.py simulate

# Check a specific memory access
python cli.py check --address 0x80001000 --access rw --privilege U --setup

# Set up standard protection
python cli.py setup

# Show memory map
python cli.py map --setup

# Configure a custom PMP entry
python cli.py configure --entry 4 --address 0x90000000 --size 0x10000 --access rw

# Show full PMP state
python cli.py status --setup
```

## Python API

```python
from simulator import PMPUnit, AccessType, PrivilegeMode, setup_standard_protection

# Create PMP unit
pmp = PMPUnit(num_entries=16)

# Configure entries
pmp.configure_entry(0, base_address=0x00000000, size=0x10000,
                    permissions=AccessType.READ | AccessType.EXECUTE, locked=True)

# Check access
allowed, reason = pmp.check_access(0x00001000, AccessType.READ, PrivilegeMode.U)

# Or use standard setup
setup_standard_protection(pmp)
```

## Standard Memory Layout

| Entry | Region | Address Range | Permissions | Notes |
|-------|--------|---------------|-------------|-------|
| 0 | ROM | 0x00000000 - 0x0000FFFF | R-X, locked | Boot code |
| 1 | RAM | 0x80000000 - 0x80FFFFFF | RW- | Main memory |
| 2 | MMIO | 0x40000000 - 0x4000FFFF | RW- | Device registers |
| 3 | Flash | 0x20000000 - 0x20FFFFFF | R-X | Firmware storage |

## Requirements

Python 3.10+ stdlib only (no external dependencies).

## License

MIT
