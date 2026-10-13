"use strict";

/* Baseline RISC-V PMP only: no Smepmp, paging, or implementation-specific grain. */
const MAX_REGISTER = (1n << 56n) - 1n;

function parseQuantity(value, name = "Value") {
  const stringValue = String(value).trim();
  if (!/^(?:0[xX][0-9a-fA-F]+|[0-9]+)$/.test(stringValue)) {
    throw new Error(name + " must be a non-negative decimal or hexadecimal integer");
  }
  return BigInt(stringValue);
}

function parsePermissions(value, allowEmpty = true) {
  const text = String(value).toUpperCase().trim();
  if (text && (!/^[RWX]+$/.test(text) || new Set(text).size !== text.length)) {
    throw new Error("Permissions must contain unique R, W, X letters");
  }
  if (!text && !allowEmpty) throw new Error("Select R, W or X access");
  if (text.includes("W") && !text.includes("R")) {
    throw new Error("R=0, W=1 is reserved in baseline PMP");
  }
  return text;
}

class PMPUnit {
  constructor(count = 16) {
    if (!Number.isInteger(count) || count < 1 || count > 64) {
      throw new Error("PMP entry count must be from 1 to 64");
    }
    this.entries = Array.from({ length: count }, () => ({
      mode: "OFF", addr: 0n, permissions: "", locked: false,
    }));
  }

  configure(index, params) {
    if (!Number.isInteger(index) || index < 0 || index >= this.entries.length) {
      throw new Error("Invalid PMP entry index");
    }
    const previous = this.entries[index];
    if (previous.locked || (
      index + 1 < this.entries.length &&
      this.entries[index + 1].locked &&
      this.entries[index + 1].mode === "TOR"
    )) {
      throw new Error("PMP entry address register is locked");
    }
    const mode = String(params.mode).toUpperCase();
    if (!["OFF", "TOR", "NA4", "NAPOT"].includes(mode)) {
      throw new Error("Unknown PMP addressing mode");
    }
    const address = parseQuantity(params.address, "Address");
    const permissions = parsePermissions(params.permissions || "");
    const locked = Boolean(params.locked);
    let addr = address >> 2n;

    if (address % 4n !== 0n) throw new Error("Address must be 4-byte aligned");
    if (mode === "NAPOT") {
      const size = parseQuantity(params.size, "Size");
      if (size < 8n || (size & (size - 1n)) !== 0n) {
        throw new Error("NAPOT size must be a power of two of at least 8 bytes");
      }
      if (address % size !== 0n) throw new Error("NAPOT base must align to its size");
      addr |= (size >> 3n) - 1n;
    }
    if (addr > MAX_REGISTER) throw new Error("Address exceeds the 56-bit PMP register");
    this.entries[index] = { mode, addr, permissions, locked };
  }

  region(index) {
    const entry = this.entries[index];
    const top = entry.addr << 2n;
    if (entry.mode === "OFF") return null;
    if (entry.mode === "TOR") {
      const lo = index ? this.entries[index - 1].addr << 2n : 0n;
      return top > lo ? { lo, hi: top } : null;
    }
    if (entry.mode === "NA4") return { lo: top, hi: top + 4n };
    let n = 0n;
    let encoded = entry.addr;
    while ((encoded & 1n) !== 0n) { n++; encoded >>= 1n; }
    const lo = (entry.addr & ~((1n << n) - 1n)) << 2n;
    return { lo, hi: lo + (1n << (n + 3n)) };
  }

  check(address, access, privilege = "M", bytes = 1) {
    const start = parseQuantity(address, "Access address");
    const size = parseQuantity(bytes, "Access size");
    if (size === 0n) throw new Error("Access size must be positive");
    const op = String(access).toUpperCase().trim();
    if (!/^[RWX]$/.test(op)) throw new Error("Access must be R, W or X");
    const mode = String(privilege).toUpperCase().trim();
    if (!["M", "S", "U"].includes(mode)) throw new Error("Privilege must be M, S or U");
    const end = start + size;

    for (let i = 0; i < this.entries.length; i++) {
      const range = this.region(i);
      if (!range || start >= range.hi || end <= range.lo) continue;
      if (start < range.lo || end > range.hi) {
        return { allowed: false, entry: i, reason: "Partial match: operation crosses PMP[" + i + "] boundary" };
      }
      const entry = this.entries[i];
      if (mode === "M" && !entry.locked) {
        return { allowed: true, entry: i, reason: "M-mode bypasses unlocked PMP[" + i + "] permissions" };
      }
      const allowed = entry.permissions.includes(op);
      return { allowed, entry: i, reason: "PMP[" + i + "] " + (allowed ? "permits " : "denies ") + op + " in " + mode + "-mode" };
    }
    return {
      allowed: mode === "M",
      entry: null,
      reason: mode === "M" ? "No match: M-mode default allow" : "No match: S/U-mode default deny",
    };
  }

  list() {
    return this.entries.map((entry, index) => {
      const range = this.region(index);
      return {
        index, mode: entry.mode, locked: entry.locked,
        permissions: entry.permissions || "—",
        pmpaddr: "0x" + entry.addr.toString(16).toUpperCase(),
        range: range
          ? "0x" + range.lo.toString(16).toUpperCase() + " – 0x" + (range.hi - 1n).toString(16).toUpperCase()
          : (entry.mode === "OFF" ? "Disabled" : "Empty TOR"),
      };
    });
  }
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { PMPUnit, parseQuantity, parsePermissions };
}
if (typeof window !== "undefined") window.PMPUnit = PMPUnit;
