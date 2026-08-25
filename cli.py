"""
CLI for RISC-V PMP (Physical Memory Protection) Simulator.

Commands:
- check: Check a memory access against PMP rules
- configure: Configure a PMP entry
- map: Show the current PMP memory map
- simulate: Run a simulation with standard protection
- status: Show full PMP state
- setup: Set up standard protection and test accesses
"""
import argparse
import sys

from simulator import (
    PMPUnit, PMPEntry, PMPMatchMode, AccessType, PrivilegeMode,
    setup_standard_protection, simulate_memory_accesses,
)


def _parse_access(s: str) -> AccessType:
    """Parse access type string like 'r', 'rw', 'rwx', etc."""
    p = AccessType.NONE
    s = s.upper()
    if 'R' in s:
        p |= AccessType.READ
    if 'W' in s:
        p |= AccessType.WRITE
    if 'X' in s:
        p |= AccessType.EXECUTE
    return p


def _parse_privilege(s: str) -> PrivilegeMode:
    """Parse privilege mode string."""
    return {'U': PrivilegeMode.U, 'S': PrivilegeMode.S, 'M': PrivilegeMode.M}[s.upper()]


def cmd_check(args):
    """Check a memory access."""
    pmp = PMPUnit(num_entries=args.entries)
    # Configure from JSON or use defaults
    if args.setup:
        setup_standard_protection(pmp)

    address = int(args.address, 0)
    access = _parse_access(args.access)
    priv = _parse_privilege(args.privilege)

    allowed, reason = pmp.check_access(address, access, priv)
    print(f"Memory Access Check:")
    print(f"  Address:    0x{address:08X}")
    print(f"  Access:     {access.name}")
    print(f"  Privilege:  {priv.name}")
    print(f"  Result:     {'ALLOWED' if allowed else 'DENIED'}")
    print(f"  Reason:     {reason}")
    return 0 if allowed else 1


def cmd_configure(args):
    """Configure a PMP entry."""
    pmp = PMPUnit(num_entries=args.entries)
    address = int(args.address, 0)
    size = int(args.size, 0)
    access = _parse_access(args.access)
    mode = PMPMatchMode[args.mode.upper()]

    entry = pmp.get_entry(args.entry)
    if mode == PMPMatchMode.NAPOT:
        ok = pmp.configure_entry(args.entry, address, size, access, args.locked)
    elif mode == PMPMatchMode.TOR:
        ok = pmp.configure_tor(args.entry, address + size, access, args.locked)
    else:
        print(f"Unsupported mode: {args.mode}")
        return 1

    if ok:
        print(f"PMP[{args.entry}] configured:")
        print(f"  Mode:        {mode.name}")
        print(f"  Address:     0x{address:08X}")
        print(f"  Size:        0x{size:X}")
        print(f"  Permissions: {access.name}")
        print(f"  Locked:      {args.locked}")
    else:
        print(f"ERROR: PMP[{args.entry}] is locked, cannot configure")
        return 1
    return 0


def cmd_map(args):
    """Show the PMP memory map."""
    pmp = PMPUnit(num_entries=args.entries)
    if args.setup:
        setup_standard_protection(pmp)

    regions = pmp.get_memory_map()
    print(f"PMP Memory Map ({len(regions)} active regions):")
    for r in regions:
        print(f"  PMP[{r['index']:2d}] {r['mode']:5s} {r['range']}  "
              f"{r['permissions']:5s}  locked={r['locked']}")
    return 0


def cmd_simulate(args):
    """Run a simulation with standard protection."""
    pmp = PMPUnit(num_entries=args.entries)
    setup_standard_protection(pmp)

    print("RISC-V PMP Simulation")
    print("=" * 60)

    # Show memory map
    print("\nMemory Map:")
    for r in pmp.get_memory_map():
        print(f"  PMP[{r['index']:2d}] {r['mode']:5s} {r['range']}  "
              f"{r['permissions']:5s}  locked={r['locked']}")

    # Run test accesses
    print("\nAccess Tests:")
    results = simulate_memory_accesses(pmp)
    for r in results:
        status = "ALLOW" if r['allowed'] else "DENY "
        print(f"  [{status}] {r['description']}")
        print(f"           {r['reason']}")

    # Summary
    allowed_count = sum(1 for r in results if r['allowed'])
    denied_count = len(results) - allowed_count
    print(f"\nSummary: {allowed_count} allowed, {denied_count} denied out of {len(results)} tests")
    return 0


def cmd_status(args):
    """Show full PMP state."""
    pmp = PMPUnit(num_entries=args.entries)
    if args.setup:
        setup_standard_protection(pmp)

    state = pmp.get_full_state()
    print(f"PMP State ({pmp.num_entries} entries):")
    for entry in state:
        print(f"  PMP[{entry['index']:2d}] cfg={entry['pmpcfg']} addr={entry['pmpaddr']} "
              f"mode={entry['mode']:5s} perm={entry['permissions']:5s} L={entry['locked']}")
    return 0


def cmd_setup(args):
    """Set up standard protection and show results."""
    pmp = PMPUnit(num_entries=args.entries)
    results = setup_standard_protection(pmp)

    print("Standard PMP Protection Setup:")
    for name, ok in results.items():
        print(f"  {name}: {'OK' if ok else 'FAILED'}")

    print(f"\nMemory Map:")
    for r in pmp.get_memory_map():
        print(f"  PMP[{r['index']:2d}] {r['mode']:5s} {r['range']}  "
              f"{r['permissions']:5s}  locked={r['locked']}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='riscv-pmp',
        description='RISC-V PMP (Physical Memory Protection) Simulator'
    )
    parser.add_argument('--entries', type=int, default=16, help='Number of PMP entries')
    sub = parser.add_subparsers(dest='command', required=True)

    # check
    p = sub.add_parser('check', help='Check memory access')
    p.add_argument('--address', type=str, required=True, help='Address (hex)')
    p.add_argument('--access', type=str, default='r', help='Access type (r, w, x, rw, rwx)')
    p.add_argument('--privilege', type=str, default='M', help='Privilege (U, S, M)')
    p.add_argument('--setup', action='store_true', help='Use standard protection setup')
    p.set_defaults(func=cmd_check)

    # configure
    p = sub.add_parser('configure', help='Configure PMP entry')
    p.add_argument('--entry', type=int, required=True, help='PMP entry index')
    p.add_argument('--address', type=str, required=True, help='Base address (hex)')
    p.add_argument('--size', type=str, required=True, help='Region size (hex)')
    p.add_argument('--access', type=str, default='rwx', help='Permissions')
    p.add_argument('--mode', choices=['napot', 'tor'], default='napot')
    p.add_argument('--locked', action='store_true')
    p.set_defaults(func=cmd_configure)

    # map
    p = sub.add_parser('map', help='Show memory map')
    p.add_argument('--setup', action='store_true', help='Use standard setup')
    p.set_defaults(func=cmd_map)

    # simulate
    p = sub.add_parser('simulate', help='Run simulation')
    p.set_defaults(func=cmd_simulate)

    # status
    p = sub.add_parser('status', help='Show PMP state')
    p.add_argument('--setup', action='store_true', help='Use standard setup')
    p.set_defaults(func=cmd_status)

    # setup
    p = sub.add_parser('setup', help='Set up standard protection')
    p.set_defaults(func=cmd_setup)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
