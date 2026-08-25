"""
RISC-V PMP (Physical Memory Protection) Simulator.

Implements realistic simulations of RISC-V PMP:
- PMP registers: pmpcfg, pmpaddr
- PMP matching: TOR (Top of Range), NA4 (Naturally Aligned 4-byte), NAPOT (Naturally Aligned Power-of-Two)
- Access permissions: R (read), W (write), X (execute)
- Priority: PMP entry 0 has highest priority
- Lock bit: L (prevents modification even in M-mode)
- Address matching logic per RISC-V Privileged Specification

Uses only Python stdlib (struct, enum, dataclasses).
"""
from typing import List, Dict, Optional, Tuple, Any
from enum import IntEnum, IntFlag
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class AccessType(IntFlag):
    """PMP access types."""
    NONE = 0
    READ = 1
    WRITE = 2
    EXECUTE = 4
    RWX = READ | WRITE | EXECUTE


class PMPMatchMode(IntEnum):
    """PMP address matching modes (encoded in pmpcfg A field)."""
    OFF = 0       # Null region (disabled)
    TOR = 1       # Top of Range
    NA4 = 2       # Naturally Aligned 4-byte region
    NAPOT = 3     # Naturally Aligned Power-of-Two


class PrivilegeMode(IntEnum):
    """RISC-V privilege modes."""
    U = 0  # User
    S = 1  # Supervisor
    H = 2  # Hypervisor (optional)
    M = 3  # Machine


# Maximum number of PMP entries (spec allows 0-64, common is 16)
MAX_PMP_ENTRIES = 16


# ---------------------------------------------------------------------------
# PMP Entry
# ---------------------------------------------------------------------------

@dataclass
class PMPEntry:
    """
    A single PMP configuration entry.

    Each entry consists of:
    - pmpcfg: configuration byte (A, X, W, R, L fields)
    - pmpaddr: address register (bits [55:0] of physical address >> 2)
    """
    index: int
    pmpcfg: int = 0          # Configuration byte
    pmpaddr: int = 0         # Address register value

    # -- pmpcfg field accessors --

    @property
    def locked(self) -> bool:
        """Lock bit (bit 7)."""
        return bool(self.pmpcfg & 0x80)

    @property
    def match_mode(self) -> PMPMatchMode:
        """Address matching mode (bits 4:3)."""
        return PMPMatchMode((self.pmpcfg >> 3) & 0x3)

    @property
    def executable(self) -> bool:
        """Execute permission (bit 2)."""
        return bool(self.pmpcfg & 0x04)

    @property
    def writable(self) -> bool:
        """Write permission (bit 1)."""
        return bool(self.pmpcfg & 0x02)

    @property
    def readable(self) -> bool:
        """Read permission (bit 0)."""
        return bool(self.pmpcfg & 0x01)

    @property
    def permissions(self) -> AccessType:
        """Get combined permissions."""
        p = AccessType.NONE
        if self.readable:
            p |= AccessType.READ
        if self.writable:
            p |= AccessType.WRITE
        if self.executable:
            p |= AccessType.EXECUTE
        return p

    def set_config(self, locked: bool = False, match_mode: PMPMatchMode = PMPMatchMode.OFF,
                   read: bool = False, write: bool = False, execute: bool = False) -> None:
        """Set the pmpcfg byte from individual fields."""
        cfg = 0
        if locked:
            cfg |= 0x80
        cfg |= (match_mode & 0x3) << 3
        if execute:
            cfg |= 0x04
        if write:
            cfg |= 0x02
        if read:
            cfg |= 0x01
        self.pmpcfg = cfg & 0xFF

    # -- Address range computation --

    def get_address_range(self) -> Tuple[int, int]:
        """
        Compute the address range [lo, hi) for this PMP entry.

        Returns (base_address, end_address).
        """
        mode = self.match_mode
        if mode == PMPMatchMode.OFF:
            return (0, 0)  # No range

        if mode == PMPMatchMode.TOR:
            # Top of Range: base = previous entry's top (or 0 for entry 0)
            # top = pmpaddr << 2
            top = self.pmpaddr << 2
            # Base is determined by the previous entry (handled by PMPUnit)
            return (0, top)  # Base set externally

        if mode == PMPMatchMode.NA4:
            # Naturally Aligned 4-byte region
            base = self.pmpaddr << 2
            return (base, base + 4)

        if mode == PMPMatchMode.NAPOT:
            # Naturally Aligned Power-of-Two
            # Find the number of trailing 1 bits in pmpaddr
            addr = self.pmpaddr
            if addr == 0:
                return (0, 0)

            # Count trailing ones
            trailing_ones = 0
            temp = addr
            while temp & 1:
                trailing_ones += 1
                temp >>= 1

            # Base address: clear trailing ones, shift left by 2
            base = (addr & ~((1 << trailing_ones) - 1)) << 2
            # Size: 2^(trailing_ones + 3) bytes
            size = 1 << (trailing_ones + 3)
            return (base, base + size)

        return (0, 0)

    def matches_address(self, address: int, prev_top: int = 0) -> bool:
        """
        Check if an address falls within this PMP entry's range.

        Args:
            address: Physical address to check
            prev_top: Top address of previous entry (for TOR mode)
        """
        mode = self.match_mode
        if mode == PMPMatchMode.OFF:
            return False

        if mode == PMPMatchMode.TOR:
            top = self.pmpaddr << 2
            return prev_top <= address < top

        if mode == PMPMatchMode.NA4:
            base = self.pmpaddr << 2
            return base <= address < base + 4

        if mode == PMPMatchMode.NAPOT:
            lo, hi = self.get_address_range()
            return lo <= address < hi

        return False

    def to_dict(self) -> Dict[str, Any]:
        lo, hi = self.get_address_range()
        return {
            'index': self.index,
            'pmpcfg': f"0x{self.pmpcfg:02X}",
            'pmpaddr': f"0x{self.pmpaddr:016X}",
            'locked': self.locked,
            'mode': self.match_mode.name,
            'permissions': str(self.permissions),
            'range': f"0x{lo:016X}-0x{hi:016X}" if self.match_mode != PMPMatchMode.OFF else "OFF",
        }


# ---------------------------------------------------------------------------
# PMP Unit
# ---------------------------------------------------------------------------

class PMPUnit:
    """
    RISC-V Physical Memory Protection Unit.

    Implements the PMP checking logic per RISC-V Privileged Specification:
    - PMP entries are checked in order of priority (entry 0 highest)
    - If no PMP entry matches and we're in S/U mode, access is denied
    - If no PMP entry matches and we're in M mode, access is allowed
    - Lock bit prevents modification even from M-mode
    """

    def __init__(self, num_entries: int = 16):
        if not 0 < num_entries <= MAX_PMP_ENTRIES:
            raise ValueError(f"num_entries must be in [1, {MAX_PMP_ENTRIES}]")
        self.num_entries = num_entries
        self._entries = [PMPEntry(index=i) for i in range(num_entries)]

    @property
    def entries(self) -> List[PMPEntry]:
        return list(self._entries)

    def get_entry(self, index: int) -> PMPEntry:
        if not 0 <= index < self.num_entries:
            raise IndexError(f"PMP entry {index} out of range [0, {self.num_entries})")
        return self._entries[index]

    def write_pmpcfg(self, index: int, value: int) -> bool:
        """
        Write to a pmpcfg register.

        Returns True if the write succeeded, False if blocked by lock bit.
        """
        entry = self._entries[index]
        if entry.locked:
            return False  # Cannot modify locked entries
        entry.pmpcfg = value & 0xFF
        return True

    def write_pmpaddr(self, index: int, value: int) -> bool:
        """
        Write to a pmpaddr register.

        Returns True if the write succeeded, False if blocked by lock bit.
        """
        entry = self._entries[index]
        if entry.locked:
            return False
        # pmpaddr is 56 bits (bits [55:0] of address >> 2)
        entry.pmpaddr = value & 0x00FFFFFFFFFFFFFF
        return True

    def configure_entry(self, index: int, base_address: int, size: int,
                        permissions: AccessType = AccessType.RWX,
                        locked: bool = False) -> bool:
        """
        Configure a PMP entry with a NAPOT region.

        Args:
            index: PMP entry index
            base_address: Base address (must be naturally aligned)
            size: Region size (must be power of 2, >= 8)
            permissions: Access permissions
            locked: Lock bit

        Returns:
            True if configuration succeeded.
        """
        if not 0 <= index < self.num_entries:
            raise IndexError(f"PMP entry {index} out of range")

        entry = self._entries[index]
        if entry.locked:
            return False

        # Validate size is power of 2 and >= 8
        if size < 8 or (size & (size - 1)) != 0:
            raise ValueError(f"Size must be power of 2 and >= 8, got {size}")

        # Validate alignment
        if base_address % size != 0:
            raise ValueError(f"Base address 0x{base_address:X} not aligned to size {size}")

        # Compute NAPOT encoding
        # pmpaddr = (base >> 2) | ((size >> 3) - 1) ... but with trailing ones
        # For NAPOT: pmpaddr = (base >> 2) with trailing 1s encoding the size
        napot_addr = (base_address >> 2) | ((size >> 3) - 1) if size > 8 else (base_address >> 2)

        entry.pmpaddr = napot_addr

        # Set config
        read = bool(permissions & AccessType.READ)
        write = bool(permissions & AccessType.WRITE)
        execute = bool(permissions & AccessType.EXECUTE)
        entry.set_config(
            locked=locked,
            match_mode=PMPMatchMode.NAPOT,
            read=read, write=write, execute=execute,
        )
        return True

    def configure_tor(self, index: int, top_address: int,
                      permissions: AccessType = AccessType.RWX,
                      locked: bool = False) -> bool:
        """
        Configure a PMP entry with TOR (Top of Range) mode.

        The base address is the top of the previous entry (or 0 for entry 0).
        """
        if not 0 <= index < self.num_entries:
            raise IndexError(f"PMP entry {index} out of range")

        entry = self._entries[index]
        if entry.locked:
            return False

        entry.pmpaddr = top_address >> 2

        read = bool(permissions & AccessType.READ)
        write = bool(permissions & AccessType.WRITE)
        execute = bool(permissions & AccessType.EXECUTE)
        entry.set_config(
            locked=locked,
            match_mode=PMPMatchMode.TOR,
            read=read, write=write, execute=execute,
        )
        return True

    def check_access(self, address: int, access_type: AccessType,
                     privilege: PrivilegeMode = PrivilegeMode.M) -> Tuple[bool, str]:
        """
        Check if a memory access is allowed.

        Per RISC-V spec:
        1. Check entries in priority order (0 = highest)
        2. If a matching entry is found:
           - Check permissions
           - If L=0 and privilege=M: always allowed (M-mode overrides)
           - If L=1 or privilege≠M: check R/W/X bits
        3. If no entry matches:
           - M-mode: allowed (default)
           - S/U-mode: denied (default)

        Returns (allowed: bool, reason: str).
        """
        prev_top = 0

        for entry in self._entries:
            if entry.match_mode == PMPMatchMode.OFF:
                if entry.match_mode == PMPMatchMode.TOR:
                    prev_top = entry.pmpaddr << 2
                continue

            if entry.matches_address(address, prev_top):
                # Found matching entry
                if privilege == PrivilegeMode.M and not entry.locked:
                    # M-mode with unlocked entry: access allowed
                    return True, f"M-mode override on PMP[{entry.index}] ({entry.match_mode.name})"

                # Check permissions
                if access_type & ~entry.permissions:
                    missing = access_type & ~entry.permissions
                    return False, (f"PMP[{entry.index}] denies {access_type.name} "
                                   f"(has {entry.permissions.name})")

                return True, f"PMP[{entry.index}] allows {access_type.name}"

            if entry.match_mode == PMPMatchMode.TOR:
                prev_top = entry.pmpaddr << 2

        # No matching entry found
        if privilege == PrivilegeMode.M:
            return True, "No PMP match, M-mode default allow"
        return False, f"No PMP match, {privilege.name}-mode default deny"

    def get_memory_map(self) -> List[Dict[str, Any]]:
        """Get the current PMP memory map."""
        return [e.to_dict() for e in self._entries if e.match_mode != PMPMatchMode.OFF]

    def get_full_state(self) -> List[Dict[str, Any]]:
        """Get full state of all PMP entries."""
        return [e.to_dict() for e in self._entries]

    def reset(self):
        """Reset all PMP entries to default state."""
        for entry in self._entries:
            if not entry.locked:
                entry.pmpcfg = 0
                entry.pmpaddr = 0


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

def setup_standard_protection(pmp: PMPUnit) -> Dict[str, Any]:
    """
    Set up a standard PMP configuration for a typical system.

    Layout:
    - Entry 0: ROM (0x00000000 - 0x0000FFFF, R-X, locked)
    - Entry 1: RAM (0x80000000 - 0x80FFFFFF, RW-)
    - Entry 2: MMIO (0x40000000 - 0x4000FFFF, RW-)
    - Entry 3: Flash (0x20000000 - 0x20FFFFFF, R-X)
    """
    results = {}

    # ROM: read-only, executable, locked
    ok = pmp.configure_entry(0, base_address=0x00000000, size=0x10000,
                             permissions=AccessType.READ | AccessType.EXECUTE,
                             locked=True)
    results['ROM'] = ok

    # RAM: read-write, not executable
    ok = pmp.configure_entry(1, base_address=0x80000000, size=0x1000000,
                             permissions=AccessType.READ | AccessType.WRITE)
    results['RAM'] = ok

    # MMIO: read-write, not executable
    ok = pmp.configure_entry(2, base_address=0x40000000, size=0x10000,
                             permissions=AccessType.READ | AccessType.WRITE)
    results['MMIO'] = ok

    # Flash: read-execute, not writable
    ok = pmp.configure_entry(3, base_address=0x20000000, size=0x1000000,
                             permissions=AccessType.READ | AccessType.EXECUTE)
    results['Flash'] = ok

    return results


def simulate_memory_accesses(pmp: PMPUnit) -> List[Dict[str, Any]]:
    """Simulate various memory accesses and show results."""
    test_cases = [
        # (address, access_type, privilege, description)
        (0x00001000, AccessType.READ, PrivilegeMode.M, "Read ROM from M-mode"),
        (0x00001000, AccessType.WRITE, PrivilegeMode.M, "Write ROM from M-mode (locked)"),
        (0x00001000, AccessType.READ, PrivilegeMode.U, "Read ROM from U-mode"),
        (0x00001000, AccessType.WRITE, PrivilegeMode.U, "Write ROM from U-mode"),
        (0x80001000, AccessType.READ, PrivilegeMode.M, "Read RAM from M-mode"),
        (0x80001000, AccessType.WRITE, PrivilegeMode.U, "Write RAM from U-mode"),
        (0x80001000, AccessType.EXECUTE, PrivilegeMode.U, "Execute RAM from U-mode"),
        (0x40000100, AccessType.READ, PrivilegeMode.M, "Read MMIO from M-mode"),
        (0x20001000, AccessType.READ, PrivilegeMode.U, "Read Flash from U-mode"),
        (0x20001000, AccessType.EXECUTE, PrivilegeMode.U, "Execute Flash from U-mode"),
        (0x20001000, AccessType.WRITE, PrivilegeMode.U, "Write Flash from U-mode"),
        (0xF0000000, AccessType.READ, PrivilegeMode.M, "Read unmapped from M-mode"),
        (0xF0000000, AccessType.READ, PrivilegeMode.U, "Read unmapped from U-mode"),
    ]

    results = []
    for addr, access, priv, desc in test_cases:
        allowed, reason = pmp.check_access(addr, access, priv)
        results.append({
            'description': desc,
            'address': f"0x{addr:08X}",
            'access': str(access),
            'privilege': priv.name,
            'allowed': allowed,
            'reason': reason,
        })
    return results
