"""
Automated Pytest Test Suite for RISC-V PMP Simulator Core.

Tests the Physical Memory Protection unit logic including:
- NAPOT and TOR address matching
- Access permission checking
- Lock bit behavior
- Privilege mode handling
- Input validation
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from simulator import (
    PMPUnit, PMPEntry, PMPMatchMode, AccessType, PrivilegeMode,
    setup_standard_protection, simulate_memory_accesses,
    MAX_PMP_ENTRIES,
)


class TestPMPUnitCreation:
    """Test PMPUnit initialization and basic properties."""

    def test_default_creation(self):
        pmp = PMPUnit()
        assert pmp.num_entries == 16
        assert len(pmp.entries) == 16

    def test_custom_entries(self):
        pmp = PMPUnit(num_entries=8)
        assert pmp.num_entries == 8
        assert len(pmp.entries) == 8

    def test_max_entries(self):
        pmp = PMPUnit(num_entries=MAX_PMP_ENTRIES)
        assert pmp.num_entries == MAX_PMP_ENTRIES

    def test_invalid_entries_zero(self):
        with pytest.raises(ValueError):
            PMPUnit(num_entries=0)

    def test_invalid_entries_negative(self):
        with pytest.raises(ValueError):
            PMPUnit(num_entries=-1)

    def test_invalid_entries_too_many(self):
        with pytest.raises(ValueError):
            PMPUnit(num_entries=MAX_PMP_ENTRIES + 1)


class TestPMPEntry:
    """Test PMPEntry configuration and properties."""

    def test_default_entry(self):
        entry = PMPEntry(index=0)
        assert entry.pmpcfg == 0
        assert entry.pmpaddr == 0
        assert not entry.locked
        assert entry.match_mode == PMPMatchMode.OFF
        assert entry.permissions == AccessType.NONE

    def test_set_config(self):
        entry = PMPEntry(index=0)
        entry.set_config(locked=True, match_mode=PMPMatchMode.NAPOT,
                         read=True, write=True, execute=True)
        assert entry.locked
        assert entry.match_mode == PMPMatchMode.NAPOT
        assert entry.readable
        assert entry.writable
        assert entry.executable
        assert entry.permissions == AccessType.RWX

    def test_napot_range_8_bytes(self):
        """NAPOT with size=8 should cover 8 bytes."""
        entry = PMPEntry(index=0)
        entry.pmpaddr = 0x1000 >> 2  # base=0x1000, size=8 (no trailing ones)
        entry.set_config(match_mode=PMPMatchMode.NAPOT)
        lo, hi = entry.get_address_range()
        assert lo == 0x1000
        assert hi == 0x1008

    def test_napot_range_64_bytes(self):
        """NAPOT with size=64 should cover 64 bytes."""
        entry = PMPEntry(index=0)
        # For 64-byte region at 0x1000: pmpaddr = (0x1000 >> 2) | ((64 >> 3) - 1) = 0x400 | 7 = 0x407
        entry.pmpaddr = (0x1000 >> 2) | ((64 >> 3) - 1)
        entry.set_config(match_mode=PMPMatchMode.NAPOT)
        lo, hi = entry.get_address_range()
        assert lo == 0x1000
        assert hi == 0x1040


class TestConfigureEntry:
    """Test PMPUnit.configure_entry method."""

    def test_configure_napot(self):
        pmp = PMPUnit()
        ok = pmp.configure_entry(0, base_address=0x1000, size=64,
                                 permissions=AccessType.READ | AccessType.WRITE)
        assert ok
        entry = pmp.get_entry(0)
        assert entry.match_mode == PMPMatchMode.NAPOT
        assert entry.readable
        assert entry.writable
        assert not entry.executable

    def test_configure_locked(self):
        pmp = PMPUnit()
        ok = pmp.configure_entry(0, base_address=0x1000, size=64,
                                 permissions=AccessType.READ | AccessType.WRITE, locked=True)
        assert ok
        entry = pmp.get_entry(0)
        assert entry.locked

    def test_configure_locked_blocks_modification(self):
        pmp = PMPUnit()
        pmp.configure_entry(0, base_address=0x1000, size=64, locked=True)
        ok = pmp.configure_entry(0, base_address=0x2000, size=64)
        assert not ok  # Should fail because entry is locked

    def test_configure_invalid_size(self):
        pmp = PMPUnit()
        with pytest.raises(ValueError, match="power of 2"):
            pmp.configure_entry(0, base_address=0x1000, size=7)

    def test_configure_invalid_alignment(self):
        pmp = PMPUnit()
        with pytest.raises(ValueError, match="not aligned"):
            pmp.configure_entry(0, base_address=0x1001, size=64)

    def test_configure_negative_address(self):
        pmp = PMPUnit()
        with pytest.raises(ValueError, match="non-negative"):
            pmp.configure_entry(0, base_address=-1, size=64)

    def test_configure_invalid_index(self):
        pmp = PMPUnit()
        with pytest.raises(IndexError):
            pmp.configure_entry(16, base_address=0x1000, size=64)


class TestConfigureTor:
    """Test PMPUnit.configure_tor method."""

    def test_configure_tor(self):
        pmp = PMPUnit()
        ok = pmp.configure_tor(0, top_address=0x1000, permissions=AccessType.READ | AccessType.WRITE)
        assert ok
        entry = pmp.get_entry(0)
        assert entry.match_mode == PMPMatchMode.TOR

    def test_configure_tor_negative_address(self):
        pmp = PMPUnit()
        with pytest.raises(ValueError, match="non-negative"):
            pmp.configure_tor(0, top_address=-1)

    def test_configure_tor_locked(self):
        pmp = PMPUnit()
        pmp.configure_tor(0, top_address=0x1000, locked=True)
        ok = pmp.configure_tor(0, top_address=0x2000)
        assert not ok


class TestCheckAccess:
    """Test PMPUnit.check_access method."""

    def test_m_mode_default_allow(self):
        """M-mode should be allowed when no PMP entry matches."""
        pmp = PMPUnit()
        allowed, reason = pmp.check_access(0x1000, AccessType.READ, PrivilegeMode.M)
        assert allowed
        assert "M-mode default allow" in reason

    def test_u_mode_default_deny(self):
        """U-mode should be denied when no PMP entry matches."""
        pmp = PMPUnit()
        allowed, reason = pmp.check_access(0x1000, AccessType.READ, PrivilegeMode.U)
        assert not allowed
        assert "default deny" in reason

    def test_s_mode_default_deny(self):
        """S-mode should be denied when no PMP entry matches."""
        pmp = PMPUnit()
        allowed, reason = pmp.check_access(0x1000, AccessType.READ, PrivilegeMode.S)
        assert not allowed

    def test_m_mode_override_unlocked(self):
        """M-mode should override unlocked entries."""
        pmp = PMPUnit()
        pmp.configure_entry(0, base_address=0x0, size=0x1000,
                           permissions=AccessType.NONE)
        allowed, reason = pmp.check_access(0x100, AccessType.READ, PrivilegeMode.M)
        assert allowed
        assert "M-mode override" in reason

    def test_locked_entry_blocks_m_mode(self):
        """Locked entries should enforce permissions even in M-mode."""
        pmp = PMPUnit()
        pmp.configure_entry(0, base_address=0x0, size=0x1000,
                           permissions=AccessType.READ, locked=True)
        # Write should be denied even in M-mode because entry is locked
        allowed, reason = pmp.check_access(0x100, AccessType.WRITE, PrivilegeMode.M)
        assert not allowed

    def test_permission_check_read(self):
        """Read access should be allowed when READ permission is set."""
        pmp = PMPUnit()
        pmp.configure_entry(0, base_address=0x0, size=0x1000,
                           permissions=AccessType.READ)
        allowed, reason = pmp.check_access(0x100, AccessType.READ, PrivilegeMode.U)
        assert allowed

    def test_permission_check_write_denied(self):
        """Write access should be denied when only READ permission is set."""
        pmp = PMPUnit()
        pmp.configure_entry(0, base_address=0x0, size=0x1000,
                           permissions=AccessType.READ)
        allowed, reason = pmp.check_access(0x100, AccessType.WRITE, PrivilegeMode.U)
        assert not allowed

    def test_negative_address_raises(self):
        """Negative address should raise ValueError."""
        pmp = PMPUnit()
        with pytest.raises(ValueError, match="non-negative"):
            pmp.check_access(-1, AccessType.READ)


class TestPriority:
    """Test PMP entry priority (entry 0 has highest priority)."""

    def test_entry_0_priority(self):
        """Entry 0 should take priority over entry 1."""
        pmp = PMPUnit()
        # Entry 0: deny all
        pmp.configure_entry(0, base_address=0x0, size=0x1000,
                           permissions=AccessType.NONE, locked=True)
        # Entry 1: allow all
        pmp.configure_entry(1, base_address=0x0, size=0x2000,
                           permissions=AccessType.RWX, locked=True)
        # Access in overlapping region should be denied (entry 0 matches first)
        allowed, reason = pmp.check_access(0x100, AccessType.READ, PrivilegeMode.U)
        assert not allowed
        assert "PMP[0]" in reason


class TestStandardProtection:
    """Test setup_standard_protection helper."""

    def test_setup_completes(self):
        pmp = PMPUnit()
        results = setup_standard_protection(pmp)
        assert all(results.values())

    def test_rom_is_locked(self):
        pmp = PMPUnit()
        setup_standard_protection(pmp)
        rom = pmp.get_entry(0)
        assert rom.locked
        assert rom.readable
        assert rom.executable
        assert not rom.writable

    def test_ram_permissions(self):
        pmp = PMPUnit()
        setup_standard_protection(pmp)
        ram = pmp.get_entry(1)
        assert ram.readable
        assert ram.writable
        assert not ram.executable

    def test_simulate_memory_accesses(self):
        pmp = PMPUnit()
        setup_standard_protection(pmp)
        results = simulate_memory_accesses(pmp)
        assert len(results) > 0
        # ROM read from M-mode should be allowed
        assert results[0]['allowed'] is True
        # ROM write from M-mode (locked) should be denied
        assert results[1]['allowed'] is False


class TestMemoryMap:
    """Test get_memory_map and get_full_state."""

    def test_memory_map_empty(self):
        pmp = PMPUnit()
        regions = pmp.get_memory_map()
        assert len(regions) == 0

    def test_memory_map_with_entries(self):
        pmp = PMPUnit()
        pmp.configure_entry(0, base_address=0x0, size=0x1000)
        regions = pmp.get_memory_map()
        assert len(regions) == 1
        assert regions[0]['index'] == 0

    def test_full_state(self):
        pmp = PMPUnit(num_entries=4)
        state = pmp.get_full_state()
        assert len(state) == 4


class TestReset:
    """Test PMPUnit reset."""

    def test_reset_clears_unlocked(self):
        pmp = PMPUnit()
        pmp.configure_entry(0, base_address=0x0, size=0x1000)
        pmp.reset()
        entry = pmp.get_entry(0)
        assert entry.match_mode == PMPMatchMode.OFF

    def test_reset_preserves_locked(self):
        pmp = PMPUnit()
        pmp.configure_entry(0, base_address=0x0, size=0x1000,
                           permissions=AccessType.READ | AccessType.WRITE, locked=True)
        pmp.reset()
        entry = pmp.get_entry(0)
        assert entry.locked
        assert entry.match_mode == PMPMatchMode.NAPOT
