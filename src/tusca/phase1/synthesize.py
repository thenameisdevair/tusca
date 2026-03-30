import asyncio
from rich.console import Console
from tusca.utils.credits import CreditTracker
from tusca.utils.markdown import timestamp, table
from tusca.models.intel import OnchainIntel, DeployerIntel, TVLIntel, TokenSignals
from tusca.phase1.etherscan import get_contract_identity
from tusca.phase1.defillama import get_protocol_tvl, get_related_hacks
from tusca.phase1.nansen import (
    get_deployer_intelligence,
    get_token_signals,
    get_smart_money_flows,
    run_agent_fast,
)

console = Console()


async def run_phase1(
    contract_address: str,
    chain: str,
    tracker: CreditTracker,
) -> OnchainIntel:
    """Orchestrate all Phase 1 data fetches and return OnchainIntel."""

    console.print(f"\n[bold cyan]TUSCA Phase 1 — Onchain Intelligence Brief[/bold cyan]")
    console.print(f"[dim]target: {contract_address} | chain: {chain}[/dim]\n")

    intel = OnchainIntel(
        contract_address=contract_address,
        chain=chain,
        timestamp=timestamp(),
    )

    # step 1 — contract identity (etherscan)
    intel.deployer = await get_contract_identity(contract_address, chain)

    # step 2 — protocol TVL (defillama)
    intel.tvl = await get_protocol_tvl(contract_address)

    # step 3 — related hacks (defillama)
    intel.related_hacks = await get_related_hacks(
        intel.tvl.category,
        intel.tvl.protocol_name,
    )

    # step 4 — deployer wallet intelligence (nansen profiler)
    deployer_data = await get_deployer_intelligence(intel.deployer.address, tracker)
    intel.deployer.labels = deployer_data.get("labels", [])
    intel.deployer.related_wallets = deployer_data.get("related_wallets", [])
    intel.deployer.counterparties = [
        c.get("address", "") for c in deployer_data.get("counterparties", [])
    ]
    intel.deployer.suspicious = deployer_data.get("suspicious", False)

    # step 5 — token signals (nansen TGM)
    intel.token_signals = await get_token_signals(contract_address, chain, tracker)

    # step 6 — smart money flows (nansen smart money)
    sm_data = await get_smart_money_flows(contract_address, chain, tracker)

    # step 7 — agent synthesis (nansen agent /fast)
    query = _build_agent_query(intel, deployer_data, sm_data)
    intel.agent_narrative = await run_agent_fast(query, tracker)

    # derive recommended threat classes from signals
    intel.recommended_threat_classes = _derive_threat_classes(intel, deployer_data)

    intel.credit_log = tracker.log

    console.print(f"\n[bold green]✓ Phase 1 complete — {tracker.spent} credits used[/bold green]\n")
    return intel


def _build_agent_query(intel: OnchainIntel, deployer_data: dict, sm_data: dict) -> str:
    """Build the natural language query for Nansen Agent."""

    hacks_summary = ""
    if intel.related_hacks:
        hacks_summary = ", ".join(
            f"{h.protocol} ({h.vuln_type}, ${h.amount_usd:,.0f})"
            for h in intel.related_hacks[:3]
        )

    suspicious_flag = ""
    if intel.deployer.suspicious:
        suspicious_flag = "The deployer wallet has counterparties connected to known exploiters or attackers."

    return f"""
I am auditing a smart contract at address {intel.contract_address} on {intel.chain}.

Protocol context:
- Name: {intel.tvl.protocol_name or 'unknown'}
- Category: {intel.tvl.category or 'unknown'}
- Current TVL: ${intel.tvl.tvl_current:,.0f}
- TVL 7d change: {intel.tvl.tvl_7d_change_pct}%
- TVL 30d change: {intel.tvl.tvl_30d_change_pct}%

Deployer: {intel.deployer.address}
- Verified contract: {intel.deployer.is_verified}
- Deployed: {intel.deployer.deploy_date}
- Transaction count: {intel.deployer.tx_count}
- {suspicious_flag}

Smart money behavior:
- Direction: {intel.token_signals.smart_money_direction}
- Net flow USD: ${intel.token_signals.net_flow_usd:,.0f}
- Fresh wallet accumulation: {intel.token_signals.fresh_wallet_accumulation}
- Suspicious holders: {len(intel.token_signals.suspicious_holders)}

Related protocol hacks in same category: {hacks_summary or 'none found'}

Based on this onchain data, what are the key risk signals present?
Are there any behavioral patterns consistent with pre-exploit staging,
smart money exit ahead of an exploit, or suspicious deployer activity?
What vulnerability classes should this audit prioritize?
""".strip()


def _derive_threat_classes(intel: OnchainIntel, deployer_data: dict) -> list[str]:
    """Derive recommended threat classes from onchain signals."""
    classes = []

    # TVL declining fast — fund drainage risk
    if intel.tvl.tvl_7d_change_pct < -10:
        classes.append("fund_drainage")

    # smart money exiting — something may be known
    if intel.token_signals.smart_money_direction == "exiting":
        classes.append("oracle_manipulation")
        classes.append("flash_loan")

    # suspicious holders or counterparties
    if intel.token_signals.suspicious_holders or intel.deployer.suspicious:
        classes.append("access_control")

    # fresh wallet accumulation — sybil / attacker staging
    if intel.token_signals.fresh_wallet_accumulation:
        classes.append("MEV_liquidation")

    # related hacks — inherit their vuln classes
    for hack in intel.related_hacks[:3]:
        vuln = hack.vuln_type.lower()
        if "oracle" in vuln and "oracle_manipulation" not in classes:
            classes.append("oracle_manipulation")
        if "reentran" in vuln and "reentrancy" not in classes:
            classes.append("reentrancy")
        if "flash" in vuln and "flash_loan" not in classes:
            classes.append("flash_loan")
        if "access" in vuln and "access_control" not in classes:
            classes.append("access_control")

    # always include accounting drift for yield/lending protocols
    if intel.tvl.category.lower() in ["yield aggregator", "lending", "cdp"]:
        if "accounting_drift" not in classes:
            classes.append("accounting_drift")

    return classes if classes else ["unknown — manual review required"]


def render_onchain_intel(intel: OnchainIntel, tracker: CreditTracker) -> str:
    """Render OnchainIntel to ONCHAIN-INTEL.md markdown string."""

    lines = []
    lines.append(f"# TUSCA Onchain Intelligence Brief")
    lines.append(f"> Target: `{intel.contract_address}` | Chain: {intel.chain} | {intel.timestamp}\n")
    lines.append("---\n")

    # section 1 — protocol identity
    lines.append("## 1. Protocol Identity\n")
    lines.append(f"| Field | Value |")
    lines.append(f"|-------|-------|")
    lines.append(f"| Contract | `{intel.contract_address}` |")
    lines.append(f"| Name | {intel.deployer.contract_name or 'unknown'} |")
    lines.append(f"| Deployer | `{intel.deployer.address}` |")
    lines.append(f"| Deployed | {intel.deployer.deploy_date or 'unknown'} |")
    lines.append(f"| Verified | {'✓ yes' if intel.deployer.is_verified else '✗ no'} |")
    lines.append(f"| Deployer Tx Count | {intel.deployer.tx_count:,} |")
    lines.append("")

    # section 2 — economic surface
    lines.append("## 2. Economic Surface\n")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Protocol | {intel.tvl.protocol_name or 'not found on DeFiLlama'} |")
    lines.append(f"| Category | {intel.tvl.category or 'unknown'} |")
    lines.append(f"| TVL Current | ${intel.tvl.tvl_current:,.0f} |")
    lines.append(f"| TVL 7d Change | {intel.tvl.tvl_7d_change_pct:+.2f}% |")
    lines.append(f"| TVL 30d Change | {intel.tvl.tvl_30d_change_pct:+.2f}% |")

    if intel.tvl.tvl_7d_change_pct < -10:
        lines.append(f"\n> ⚠ **Risk flag:** TVL declining {intel.tvl.tvl_7d_change_pct:.1f}% in 7 days with no public explanation.")
    lines.append("")

    # section 3 — historical hack patterns
    lines.append("## 3. Historical Hack Patterns\n")
    if intel.related_hacks:
        lines.append(f"Found {len(intel.related_hacks)} related hacks in category '{intel.tvl.category}':\n")
        lines.append("| Protocol | Date | Amount Lost | Vulnerability | Technique |")
        lines.append("|----------|------|-------------|---------------|-----------|")
        for h in intel.related_hacks:
            lines.append(f"| {h.protocol} | {h.date} | ${h.amount_usd:,.0f} | {h.vuln_type} | {h.technique} |")
    else:
        lines.append("No related hacks found for this category.")
    lines.append("")

    # section 4 — deployer trust signals
    lines.append("## 4. Deployer Trust Signals\n")
    trust_flag = "🔴 SUSPICIOUS" if intel.deployer.suspicious else "🟢 CLEAN"
    lines.append(f"**Verdict: {trust_flag}**\n")

    if intel.deployer.labels:
        lines.append(f"- Labels: {', '.join(intel.deployer.labels)}")
    if intel.deployer.related_wallets:
        lines.append(f"- Related wallets: {len(intel.deployer.related_wallets)}")
        for w in intel.deployer.related_wallets[:5]:
            lines.append(f"  - `{w}`")
    if intel.deployer.suspicious:
        lines.append(f"\n> ⚠ Deployer counterparties include addresses labeled as exploiters or attackers.")
    lines.append("")

    # section 5 — smart money behavior
    lines.append("## 5. Smart Money Behavior\n")
    direction_emoji = {
        "accumulating": "🟢",
        "exiting": "🔴",
        "neutral": "🟡",
    }.get(intel.token_signals.smart_money_direction, "⚪")

    lines.append(f"| Signal | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Direction | {direction_emoji} {intel.token_signals.smart_money_direction} |")
    lines.append(f"| Net Flow USD | ${intel.token_signals.net_flow_usd:,.0f} |")
    lines.append(f"| Fresh Wallet Accumulation | {'⚠ yes' if intel.token_signals.fresh_wallet_accumulation else 'no'} |")
    lines.append(f"| Notable Holders | {len(intel.token_signals.notable_holders)} |")
    lines.append(f"| Suspicious Holders | {len(intel.token_signals.suspicious_holders)} |")

    if intel.token_signals.suspicious_holders:
        lines.append(f"\n**Suspicious holders:**")
        for h in intel.token_signals.suspicious_holders:
            lines.append(f"- `{h}`")

    if intel.token_signals.smart_money_direction == "exiting":
        lines.append(f"\n> ⚠ **Risk flag:** Smart money is exiting. This pattern has preceded exploits in similar protocols.")
    lines.append("")

    # section 6 — onchain risk narrative
    lines.append("## 6. Onchain Risk Narrative\n")
    lines.append(intel.agent_narrative or "_Agent synthesis unavailable._")
    lines.append("")

    # section 7 — recommended threat classes
    lines.append("## 7. Recommended Threat Classes\n")
    lines.append("Derived from onchain signals — feed into PrePosv for prioritized question generation:\n")
    for i, tc in enumerate(intel.recommended_threat_classes, 1):
        lines.append(f"{i}. `{tc}`")
    lines.append("")

    # credit usage
    lines.append("---\n")
    lines.append(tracker.summary())

    return "\n".join(lines)