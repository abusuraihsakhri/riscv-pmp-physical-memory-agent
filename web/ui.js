"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const byId = id => document.getElementById(id);
  let pmp = new window.PMPUnit(16);
  let lastCheck = null;

  function renderMap() {
    const body = byId("map");
    body.replaceChildren();
    const entries = pmp.list();
    byId("count").textContent = "(" + entries.filter(e => e.mode !== "OFF").length + " active / 16)";
    for (const entry of entries) {
      const tr = document.createElement("tr");
      const values = [entry.index, entry.mode, entry.pmpaddr, entry.range, entry.permissions, entry.locked ? "Yes" : "No"];
      for (const value of values) {
        const td = document.createElement("td");
        td.textContent = String(value);
        tr.appendChild(td);
      }
      body.appendChild(tr);
    }
  }

  function setResult(check, details) {
    const el = byId("result");
    el.className = "output" + (check ? (check.allowed ? " result-ok" : " result-deny") : "");
    el.textContent = check
      ? (check.allowed ? "ALLOWED" : "DENIED") + "\n" + check.reason +
        "\nOperation: " + details.access + ", " + details.privilege + "-mode, " +
        details.bytes + " byte(s) at " + details.address
      : "Choose an operation and evaluate it against the current PMP configuration.";
  }

  function setUnit(unit) {
    pmp = unit;
    lastCheck = null;
    byId("config-error").textContent = "";
    byId("check-error").textContent = "";
    setResult(null);
    renderMap();
  }

  function example() {
    const unit = new window.PMPUnit(16);
    unit.configure(0, {mode:"NAPOT", address:"0", size:"0x10000", permissions:"RX", locked:true});
    unit.configure(1, {mode:"NAPOT", address:"0x80000000", size:"0x1000000", permissions:"RW"});
    unit.configure(2, {mode:"NAPOT", address:"0x40000000", size:"0x10000", permissions:"RW"});
    unit.configure(3, {mode:"NAPOT", address:"0x20000000", size:"0x1000000", permissions:"RX"});
    setUnit(unit);
  }

  byId("mode").addEventListener("change", () => {
    const napot = byId("mode").value === "NAPOT";
    byId("size").disabled = !napot;
    byId("size").required = napot;
  });

  byId("config-form").addEventListener("submit", event => {
    event.preventDefault();
    byId("config-error").textContent = "";
    try {
      const index = byId("index").valueAsNumber;
      pmp.configure(index, {
        mode: byId("mode").value,
        address: byId("address").value,
        size: byId("size").value,
        permissions: byId("permissions").value,
        locked: byId("locked").checked,
      });
      lastCheck = null;
      setResult(null);
      renderMap();
    } catch (error) {
      byId("config-error").textContent = error.message;
    }
  });

  byId("check-form").addEventListener("submit", event => {
    event.preventDefault();
    byId("check-error").textContent = "";
    try {
      const details = {
        address: byId("access-address").value,
        access: byId("access-type").value,
        privilege: byId("privilege").value,
        bytes: byId("bytes").value,
      };
      const check = pmp.check(details.address, details.access, details.privilege, details.bytes);
      lastCheck = { ...details, ...check };
      setResult(check, details);
    } catch (error) {
      lastCheck = null;
      setResult(null);
      byId("check-error").textContent = error.message;
    }
  });

  byId("example").addEventListener("click", example);
  byId("reset").addEventListener("click", () => setUnit(new window.PMPUnit(16)));
  byId("export").addEventListener("click", () => {
    const report = {
      model: "Baseline RISC-V PMP, without Smepmp, translation or implementation-specific grain",
      entries: pmp.list(), last_check: lastCheck,
    };
    const blob = new Blob([JSON.stringify(report, null, 2) + "\n"], {type:"application/json"});
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "riscv-pmp-report.json";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  });

  example();
});
