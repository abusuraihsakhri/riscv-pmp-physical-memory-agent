"""Regression coverage for baseline PMP matching, locking and audit integrity."""
import pytest

from agents.base import AuditTrail
from simulator import AccessType, PMPMatchMode, PMPUnit, PrivilegeMode


def test_zero_encoded_napot_is_eight_bytes():
    unit = PMPUnit()
    assert unit.configure_entry(0, 0, 8, AccessType.READ, locked=True)
    assert unit.get_entry(0).pmpaddr == 0
    assert unit.get_entry(0).get_address_range() == (0, 8)
    assert unit.check_access(0, AccessType.READ, PrivilegeMode.U)[0]
    assert unit.check_access(7, AccessType.READ, PrivilegeMode.U)[0]
    assert not unit.check_access(8, AccessType.READ, PrivilegeMode.U)[0]


def test_tor_uses_preceding_register_regardless_of_previous_mode():
    unit = PMPUnit(2)
    assert unit.write_pmpaddr(0, 0x1000 >> 2)
    assert unit.configure_tor(1, 0x2000, AccessType.READ, locked=True)
    assert not unit.check_access(0x0FFF, AccessType.READ, PrivilegeMode.U)[0]
    assert unit.check_access(0x1000, AccessType.READ, PrivilegeMode.U)[0]
    assert not unit.check_access(0x2000, AccessType.READ, PrivilegeMode.U)[0]
    assert unit.get_memory_map()[0]["range"].startswith("0x0000000000001000")
    assert not unit.write_pmpaddr(0, 0x800 >> 2)
    assert not unit.configure_entry(0, 0, 0x1000)


def test_tor_uses_previous_address_register_after_napot():
    unit = PMPUnit(2)
    unit.configure_entry(0, 0x1000, 8, AccessType.NONE, locked=False)
    unit.configure_tor(1, 0x2000, AccessType.READ, locked=True)
    # pmpaddr[0] is 0x400, yielding a TOR lower bound of 0x1000.
    assert unit.check_access(0x1008, AccessType.READ, PrivilegeMode.U)[0]
    assert not unit.check_access(0x800, AccessType.READ, PrivilegeMode.U)[0]


def test_partial_match_denied_even_for_unlocked_m_mode():
    unit = PMPUnit()
    unit.configure_entry(0, 0x1000, 8, AccessType.RWX)
    assert not unit.check_access(0x0FFC, AccessType.READ, PrivilegeMode.M, size=8)[0]
    assert not unit.check_access(0x1004, AccessType.READ, PrivilegeMode.M, size=8)[0]
    assert unit.check_access(0x1000, AccessType.READ, PrivilegeMode.M, size=8)[0]


def test_priority_first_entry_intersecting_any_byte():
    unit = PMPUnit(2)
    unit.configure_entry(0, 0, 8, AccessType.READ, locked=True)
    unit.configure_entry(1, 0, 64, AccessType.RWX, locked=True)
    assert not unit.check_access(6, AccessType.WRITE, PrivilegeMode.U, size=4)[0]
    assert unit.check_access(12, AccessType.WRITE, PrivilegeMode.U, size=4)[0]


@pytest.mark.parametrize("size", [0, -1])
def test_invalid_operation_sizes(size):
    with pytest.raises(ValueError, match="positive"):
        PMPUnit().check_access(0, AccessType.READ, size=size)


def test_empty_access_type_fails_closed():
    with pytest.raises(ValueError, match="Access type"):
        PMPUnit().check_access(0, AccessType.NONE)


def test_audit_hmac_detects_mutation_without_chain_changes():
    trail = AuditTrail(secret_key="local-regression-secret")
    trail.log("tester", "unit", "CHECK", {"value": 1})
    trail.log("tester", "unit", "CHECK", {"value": 2})
    assert trail.verify_integrity()
    trail.logs[0]["actor"] = "altered"
    assert not trail.verify_integrity()


def test_audit_snapshots_cannot_mutate_recorded_entries():
    trail = AuditTrail(secret_key="local-regression-secret")
    trail.log("tester", "unit", "CHECK", {"value": 1})
    copy = trail.get_trail()
    copy[0]["actor"] = "altered"
    assert trail.verify_integrity()
