# TUSCA — Product Requirements Document
> Threat Understanding via Smart Contract Analytics  
> Author: thenameisdevair | Status: v0.1 Draft | Updated: 2026-03-30

---

## 1. What TUSCA Is

TUSCA is a standalone CLI tool that gives smart contract auditors and bug bounty hunters onchain intelligence about their audit targets — before they read a line of code, and after they find a bug.

It is not a scanner. It is not a dashboard. It is an intelligence layer that answers two questions no existing audit tool asks:

- **Before audit:** what does onchain reality say about this protocol's risk surface?
- **After a finding:** has this vulnerability already been touched, probed, or exploited quietly in the wild?

TUSCA is built to slot into an existing audit pipeline:
```
TUSCA Phase 1 → PrePosv → pashov → DeTest → TUSCA Phase 2 → HackenProof
```

It is also useful standalone — any auditor or researcher can run it against any contract address.

---

## 2. The Problem

Current smart contract audit tooling is entirely code-local. Slither, pashov, Halmos, Medusa — they all operate on Solidity source. They have no awareness of:

- whether smart money is quietly exiting the protocol
- whether the deployer wallet is connected to known bad actors
- whether someone has already probed the vulnerability on mainnet
- whether the protocol's TVL drop is a market signal or a pre-exploit drain

Auditors look this up manually, inconsistently, or not at all. TUSCA automates it and structures it into audit-ready output.

---

## 3. Users

**Primary:** Smart contract security researchers and bug bounty hunters running manual audits against live protocols (Code4rena, Sherlock, Immunefi, HackenProof).

**Secondary:** Protocol teams doing pre-launch security reviews. Security firms doing due diligence.

---

## 4. Core Design Principles

1. **Onchain-first.** TUSCA never reads Solidity. It reads behavior.
2. **Audit-native output.** Every output file is designed to feed the next tool in the pipeline, not to be read in isolation.
3. **Explicit data provenance.** Every signal in the output is attributed to its source — Nansen, Etherscan, DeFiLlama, etc.
4. **Credit-aware.** Nansen API credits are finite. TUSCA uses cheap endpoints first, expensive endpoints only when necessary.
5. **Standalone first, pipeline-ready always.** Works as a single command. Integrates cleanly with PrePosv and pashov output.

---

## 5. Two-Phase Architecture

### Phase 1 — Onchain Intelligence Brief
**Trigger:** user provides a contract address before audit begins  
**Input:** `<contract_address> --chain <chain>`  
**Output:** `ONCHAIN-INTEL.md`  
**Feeds into:** PrePosv (enriches threat model context)

### Phase 2 — Exploit Precursor Detection
**Trigger:** pashov/SPECTRA returns findings  
**Input:** `<contract_address> --finding-file <path_to_findings.md>`  
**Output:** `EXPLOIT-PRECURSOR-REPORT.md`  
**Feeds into:** HackenProof triage / submission context

---

## 6. Phase 1 — Detailed Spec

### 6.1 Command
```bash
tusca analyze <contract_address> --chain <chain> --out <output_dir>
```

### 6.2 Data Sources & Call Sequence

| Step | Tool | Call | Credits | Output |
|------|------|------|---------|--------|
| 1.1 | Etherscan API | contract ABI, deployer address, deploy tx, verified status | free | deployer_address, deploy_date, is_verified |
| 1.2 | DeFiLlama API | protocol metadata, TVL current + history | free | tvl_current, tvl_7d_change, tvl_30d_change, category |
| 1.3 | DeFiLlama /hacks | full hacks DB, filter by category + architecture | free | related_hacks[] |
| 1.4 | Nansen Profiler | deployer: balance, transactions, related wallets, counterparties | 1–5 | deployer_trust_signals |
| 1.5 | Nansen TGM | token info, flow intelligence, who-bought-sold, top holders | 1–5 | token_signals, notable_holders |
| 1.6 | Nansen Smart Money | netflows + DEX trades for this token | 5 | smart_money_direction |
| 1.7 | Nansen Agent /fast | synthesize all above into onchain risk narrative | 200 | agent_narrative |

**Total credit cost per Phase 1 run: ~215–220 credits**

### 6.3 Output: `ONCHAIN-INTEL.md`
```
# TUSCA Onchain Intelligence Brief
## Target: <contract_address> | Chain: <chain> | Date: <timestamp>

### 1. Protocol Identity
- Contract name, deployer, deploy date, verified: yes/no

### 2. Economic Surface
- TVL current, 7d change, 30d change, category
- Risk flag if TVL declining with no public explanation

### 3. Historical Hack Patterns
- Related protocols hacked with same architecture/category
- Vulnerability types, amounts lost, dates

### 4. Deployer Trust Signals
- Deployer wallet age, tx count, labels (if any)
- Related wallets and their labels
- Top counterparties — any labeled exploiters?

### 5. Smart Money Behavior
- Net flow direction (accumulating / exiting / neutral)
- Notable labeled holders
- Any fresh wallet accumulation patterns

### 6. Onchain Risk Narrative
- [Nansen Agent synthesis]

### 7. Recommended Threat Classes
- Derived from sections 3–6, ordered by onchain signal strength
- Feeds directly into PrePosv dynamic question generation
```

---

## 7. Phase 2 — Detailed Spec

### 7.1 Command
```bash
tusca probe <contract_address> --finding-file <path> --chain <chain> --out <output_dir>
```

### 7.2 Finding Parser

TUSCA reads the findings file (pashov x-ray.md or SPECTRA output) and extracts:
```
{
  finding_id,
  severity,
  vuln_class,        // oracle_manipulation | access_control | reentrancy | 
                     // flash_loan | MEV | accounting_drift | fund_drainage
  affected_function,
  description
}
```

Each `vuln_class` maps to a specific probe strategy (see 7.3).

### 7.3 Vulnerability Class → Probe Strategy Map

**oracle_manipulation**
- Etherscan: txs to affected function during known depeg/volatility windows
- Nansen TGM: DEX trade anomalies around token during those windows
- 4byte: decode calldata of suspicious txs
- Tenderly: simulate top suspicious txs against current state

**access_control**
- Etherscan: historical calls to privileged functions (setX, transferOwnership, etc.)
- Nansen Profiler: label every address that ever called those functions
- question: has the admin key been used suspiciously or sold?

**reentrancy**
- Etherscan: failed txs to affected function with repeated call patterns
- 4byte: decode calldata for recursive call signatures
- Tenderly: replay failed txs to check if they now succeed

**flash_loan**
- Etherscan: large flash loan draws against the protocol
- Nansen TGM: capital staging signals — sudden large inflows 24–72h before suspicious activity
- Nansen Profiler: profile flash loan callers

**MEV / liquidation_race**
- Etherscan: who has called permissionless liquidation functions historically
- Nansen Profiler labels: are known MEV bots already watching this contract?
- Nansen Smart Money DEX trades: sandwich patterns around liquidation events

**accounting_drift / fund_drainage**
- Etherscan: internal txs for unexpected value movements
- Nansen TGM flows: sudden outflow spikes not explained by normal user activity
- DeFiLlama TVL: cross-reference TVL drops with suspicious tx timestamps

### 7.4 Data Sources & Call Sequence

| Step | Tool | Call | Credits | Output |
|------|------|------|---------|--------|
| 2.1 | Etherscan API | all txs + failed txs + internal txs (90d) | free | tx_history, failed_txs |
| 2.2 | 4byte.directory | decode function selectors from suspicious txs | free | decoded_calldata[] |
| 2.3 | Nansen Profiler | labels + related wallets on flagged senders | 1–100 | flagged_senders[] |
| 2.4 | Nansen TGM | DEX trades + flow anomalies around contract token | 1–5 | trade_anomalies, flow_spikes |
| 2.5 | Tenderly API | simulate top suspicious failed txs | free tier | simulation_results[] |
| 2.6 | Nansen Agent /expert | synthesize all above into precursor verdict | 750 | expert_analysis, verdict |

**Total credit cost per Phase 2 run: ~760–860 credits**

### 7.5 Output: `EXPLOIT-PRECURSOR-REPORT.md`
```
# TUSCA Exploit Precursor Report
## Finding: <vuln_class> | Target: <contract_address> | Date: <timestamp>

### 1. Finding Summary
- Vulnerability class, severity, affected function (from pashov input)

### 2. Suspicious Transaction Analysis
- Failed txs matching the attack pattern
- Timeline, senders, decoded calldata

### 3. Flagged Address Profiles
- Nansen labels for each suspicious sender
- Related wallet connections to known exploiters

### 4. Capital Staging Signals
- Unusual inflows / DEX activity in window before suspicious txs
- Flash loan draw patterns

### 5. Simulation Results
- Which suspicious txs now succeed against current state
- What state changes they would produce

### 6. Verdict
CLEAN     — no onchain evidence of probing or staging
PROBED    — evidence of failed attempts, no successful exploit
STAGED    — capital staging + probing pattern detected, high urgency
EXPLOITED — evidence of successful quiet exploit, escalate immediately

### 7. Confidence: HIGH / MEDIUM / LOW

### 8. Recommended Action
- CLEAN: proceed normally
- PROBED: accelerate submission timeline
- STAGED: submit immediately, notify protocol
- EXPLOITED: immediate disclosure, contact protocol emergency channel
```

---

## 8. Technical Stack

| Component | Choice | Reason |
|-----------|--------|--------|
| Language | Python 3.11+ | consistent with SPECTRA, rich HTTP/async ecosystem |
| HTTP | httpx (async) | handles SSE streaming for Nansen agent endpoints |
| CLI framework | Typer | clean, type-safe CLI with minimal boilerplate |
| Output | Markdown + JSON | markdown for humans, JSON for pipeline consumption |
| Config | .env + env vars | NANSEN_API_KEY, ETHERSCAN_API_KEY, TENDERLY credentials |
| Package mgr | pip + pyproject.toml | standard, installable as `tusca` command |

---

## 9. Repo Structure
```
tusca/
├── docs/
│   ├── PRD.md              # this document
│   ├── FLOW.md             # visual flow diagram
│   └── CHANGELOG.md        # version history
├── src/
│   └── tusca/
│       ├── __init__.py
│       ├── cli.py          # Typer CLI entrypoint
│       ├── phase1/
│       │   ├── __init__.py
│       │   ├── etherscan.py
│       │   ├── defillama.py
│       │   ├── nansen.py
│       │   └── synthesize.py
│       ├── phase2/
│       │   ├── __init__.py
│       │   ├── parser.py       # pashov finding parser
│       │   ├── probe_map.py    # vuln_class → strategy map
│       │   ├── etherscan.py
│       │   ├── fourbyte.py
│       │   ├── nansen.py
│       │   ├── tenderly.py
│       │   └── synthesize.py
│       ├── models/
│       │   ├── finding.py      # Finding dataclass
│       │   └── intel.py        # OnchainIntel dataclass
│       └── utils/
│           ├── config.py
│           ├── markdown.py     # output renderer
│           └── credits.py      # credit budget tracker
├── tests/
├── .env.example
├── pyproject.toml
└── README.md
```

---

## 10. API Keys Required

| Service | Key | Free Tier | Where |
|---------|-----|-----------|-------|
| Nansen | NANSEN_API_KEY | paid (challenge credits) | nansen.ai |
| Etherscan | ETHERSCAN_API_KEY | 5 calls/sec, 100k/day | etherscan.io |
| Tenderly | TENDERLY_ACCESS_KEY | 500 tx simulations/month | tenderly.co |
| DeFiLlama | none | fully free, no key | — |
| 4byte.directory | none | fully free, no key | — |

---

## 11. Challenge Submission Checklist

- [ ] `tusca analyze` runs end to end against a real contract
- [ ] `tusca probe` runs end to end against a real finding
- [ ] minimum 10 Nansen API calls logged and provable
- [ ] GitHub repo public with clean README
- [ ] demo video showing pipeline run (Phase 1 → PrePosv handoff → Phase 2)
- [ ] X post tagging @nansen_ai with #NansenCLI
- [ ] ONCHAIN-INTEL.md and EXPLOIT-PRECURSOR-REPORT.md shown in demo

---

## 12. Out of Scope (v0.1)

- Solana / non-EVM chains (Ethereum + EVM only for now)
- Real-time monitoring / alerting
- Web UI
- Automated PrePosv invocation (handoff is file-based, not automated)
- Token required — TUSCA has no token, no points, no gamification

---

## 13. Success Criteria

TUSCA wins the challenge if judges see:
1. a real auditor solving a real problem they have every day
2. Nansen data doing something no dashboard shows — security intelligence
3. a tool they could actually install and use tomorrow
4. a demo that tells a story from contract address to submission-ready report