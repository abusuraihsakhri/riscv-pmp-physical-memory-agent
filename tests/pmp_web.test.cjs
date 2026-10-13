"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { PMPUnit } = require("../web/pmp.js");

test("NAPOT zero encodes an 8-byte region, not an empty one", () => {
  const p = new PMPUnit();
  p.configure(0, { mode: "NAPOT", address: "0", size: "8", permissions: "R", locked: true });
  assert.equal(p.check("0", "R", "U").allowed, true);
  assert.equal(p.check("7", "R", "U").allowed, true);
  assert.equal(p.check("8", "R", "U").allowed, false);
});

test("TOR lower bound uses predecessor address register even if OFF", () => {
  const p = new PMPUnit(2);
  p.configure(0, { mode: "OFF", address: "0x1000" });
  p.configure(1, { mode: "TOR", address: "0x2000", permissions: "R", locked: true });
  assert.equal(p.check("0xFFF", "R", "U").allowed, false);
  assert.equal(p.check("0x1000", "R", "U").allowed, true);
  assert.equal(p.check("0x1FFF", "R", "U").allowed, true);
  assert.equal(p.check("0x2000", "R", "U").allowed, false);
  assert.throws(() => p.configure(0, { mode: "OFF", address: "0x800" }), /locked/);
});

test("partial overlap denies even with M-mode bypass", () => {
  const p = new PMPUnit();
  p.configure(0, { mode: "NA4", address: "0x1000", permissions: "RW", locked: false });
  assert.equal(p.check("0xFFE", "R", "M", 4).allowed, false);
  assert.equal(p.check("0x1000", "R", "M", 4).allowed, true);
});

test("earlier PMP entry wins and locked rules constrain M-mode", () => {
  const p = new PMPUnit(2);
  p.configure(0, { mode: "NAPOT", address: 0, size: 64, permissions: "R", locked: true });
  p.configure(1, { mode: "NAPOT", address: 0, size: 128, permissions: "RW", locked: false });
  assert.equal(p.check(12, "W", "M").allowed, false);
  assert.equal(p.check(96, "W", "U").allowed, true);
  assert.equal(p.check(62, "R", "U", 4).allowed, false);
});

test("rejects invalid sizes, alignment, and unsupported R/W combinations", () => {
  const p = new PMPUnit(2);
  assert.throws(() => p.configure(0, {mode:"NAPOT", address: 4, size: 16, permissions: "R"}), /align/);
  assert.throws(() => p.configure(0, {mode:"NAPOT", address: 0, size: 7, permissions: "R"}), /power of two/);
  assert.throws(() => p.configure(0, {mode:"NAPOT", address: 0, size: 8, permissions: "W"}), /reserved/);
  assert.throws(() => p.check(-1, "R", "U"), /non-negative/);
  assert.throws(() => p.check(0, "R", "U", 0), /positive/);
});
