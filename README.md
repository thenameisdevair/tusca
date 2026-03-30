# TUSCA
**Threat Understanding via Smart Contract Analytics**

Onchain intelligence layer for smart contract auditors and bug bounty hunters.

TUSCA answers two questions no existing audit tool asks:
- **Before audit:** what does onchain reality say about this protocol's risk surface?
- **After a finding:** has this vulnerability already been touched or probed in the wild?

---

## Pipeline Position
```
tusca analyze   →   PrePosv   →   pashov   →   DeTest   →   tusca probe   →   HackenProof
```

---

## Installation
```bash
git clone https://github.com/thenameisdevair/tusca
cd tusca
pip install -e .
```

Copy and fill in your API keys:
```bash
cp .env.example .env
```

---

## Usage

### Phase 1 — Onchain Intelligence Brief
```bash
tusca analyze <contract_address> --chain ethereum
```

Outputs `ONCHAIN-INTEL.md` — feeds into PrePosv before threat modeling.

### Phase 2 — Exploit Precursor Detection
```bash
tusca probe <contract_address> --finding-file ./x-ray.md --chain ethereum
```

Outputs `EXPLOIT-PRECURSOR-REPORT.md` — feeds into HackenProof triage.

---

## API Keys Required

| Service | Required | Free Tier |
|---------|----------|-----------|
| Nansen | yes | via challenge credits |
| Etherscan | yes | 100k calls/day |
| Tenderly | optional | 500 simulations/month |
| DeFiLlama | no key needed | fully free |
| 4byte.directory | no key needed | fully free |

---

## Data Sources

- **Nansen** — wallet labels, smart money flows, token intelligence, agent synthesis
- **Etherscan** — contract identity, deployer, transaction history, failed txs
- **DeFiLlama** — TVL, protocol metadata, hack history database
- **4byte.directory** — calldata function selector decoding
- **Tenderly** — transaction simulation against live state

---

## Output Files

| File | Phase | Fed Into |
|------|-------|----------|
| `ONCHAIN-INTEL.md` | 1 | PrePosv, THREAT-MODEL.md |
| `EXPLOIT-PRECURSOR-REPORT.md` | 2 | HackenProof submission |

---

## Built for the Nansen CLI Build Challenge — Week 3
*#NansenCLI @nansen_ai*