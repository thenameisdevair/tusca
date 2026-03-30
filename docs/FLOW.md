# TUSCA — System Flow

> Visual reference for the full data flow across both phases.

---

## Full Pipeline Position
```
contract_address
       │
       ▼
┌─────────────────┐
│  TUSCA Phase 1  │  ← onchain reality check
│  tusca analyze  │
└────────┬────────┘
         │ ONCHAIN-INTEL.md
         ▼
┌─────────────────┐
│    PrePosv      │  ← code-aware threat modeling
│  (enriched)     │
└────────┬────────┘
         │ THREAT-MODEL.md
         ▼
┌─────────────────┐
│  pashov x-ray   │  ← static audit + git analysis
└────────┬────────┘
         │ x-ray.md (findings)
         ▼
┌─────────────────┐
│    DeTest       │  ← "is the bug real?"
└────────┬────────┘
         │ verified findings
         ▼
┌─────────────────┐
│  TUSCA Phase 2  │  ← "has it been touched?"
│  tusca probe    │
└────────┬────────┘
         │ EXPLOIT-PRECURSOR-REPORT.md
         ▼
┌─────────────────┐
│   HackenProof   │  ← submission with full evidence stack
└─────────────────┘
```

---

## Phase 1 Internal Flow
```
tusca analyze <address> --chain ethereum
       │
       ├─── Etherscan ──────── deployer, deploy date, verified status
       │                              │
       ├─── DeFiLlama ─────── TVL, category, hack history
       │                              │
       ├─── Nansen Profiler ── deployer wallet intelligence
       │         (1–5 cr)             │
       ├─── Nansen TGM ─────── token flows, holders, who-bought-sold
       │         (1–5 cr)             │
       ├─── Nansen Smart Money  netflows + DEX trades
       │         (5 cr)               │
       └─── Nansen Agent/fast ─ synthesize → onchain risk narrative
                 (200 cr)             │
                                      ▼
                             ONCHAIN-INTEL.md
```

---

## Phase 2 Internal Flow
```
tusca probe <address> --finding-file x-ray.md --chain ethereum
       │
       ├─── Finding Parser
       │         └── extract: vuln_class, severity, affected_function
       │                              │
       ├─── Probe Strategy Map
       │         └── vuln_class → which tools to call
       │                              │
       ├─── Etherscan ──────── all txs + failed txs (90d)
       │                              │
       ├─── 4byte.directory ── decode calldata of suspicious txs
       │                              │
       ├─── Nansen Profiler ── label flagged senders
       │         (1–100 cr)           │
       ├─── Nansen TGM ─────── DEX anomalies + flow spikes
       │         (1–5 cr)             │
       ├─── Tenderly ──────── simulate suspicious failed txs
       │                              │
       └─── Nansen Agent/expert synthesize → precursor verdict
                 (750 cr)             │
                                      ▼
                         EXPLOIT-PRECURSOR-REPORT.md
```

---

## Vulnerability Class → Probe Strategy

| vuln_class | Etherscan | 4byte | Nansen Profiler | Nansen TGM | Tenderly |
|------------|-----------|-------|-----------------|------------|----------|
| oracle_manipulation | depeg window txs | ✓ | flagged senders | DEX anomalies | simulate failed |
| access_control | privileged fn calls | ✓ | label all callers | — | — |
| reentrancy | failed txs | recursive sigs | flagged senders | — | replay failed |
| flash_loan | large draws | ✓ | profile callers | capital staging | — |
| MEV / liquidation | permissionless fn calls | ✓ | MEV bot labels | sandwich patterns | — |
| accounting_drift | internal txs | ✓ | — | outflow spikes | — |
| fund_drainage | internal txs | ✓ | flagged receivers | TVL vs tx cross-ref | simulate |

---

## Credit Budget Per Run

| Phase | Calls | Credits |
|-------|-------|---------|
| Phase 1 | ~7 Nansen calls | ~215–220 cr |
| Phase 2 | ~3–4 Nansen calls | ~760–860 cr |
| Both phases | ~10–11 Nansen calls | ~975–1080 cr |

*Free tier calls (Etherscan, DeFiLlama, 4byte, Tenderly) are unlimited for our purposes.*

---

## Output Files

| File | Phase | Fed Into |
|------|-------|----------|
| `ONCHAIN-INTEL.md` | 1 | PrePosv context, THREAT-MODEL.md |
| `EXPLOIT-PRECURSOR-REPORT.md` | 2 | HackenProof submission, triage decision |