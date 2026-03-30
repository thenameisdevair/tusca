import asyncio
from rich.console import Console
from tusca.utils.config import config
from tusca.utils.credits import CreditTracker
from tusca.utils.markdown import timestamp
from tusca.models.intel import OnchainIntel, DeployerIntel, TVLIntel, TokenSignals
from tusca.phase1.etherscan import get_contract_identity
from tusca.phase1.defillama import get_protocol_tvl, get_related_hacks
from tusca.phase1.nansen import (
    get_deployer_intelligence,
    get_token_signals,
    get_smart_money_flows,
)

console = Console()


async def synthesize_with_claude(intel: OnchainIntel, deployer_data: dict, sm_data: dict) -> str:
    """Generate security-focused risk narrative from onchain signals."""
    console.print(f"[cyan]→ TUSCA: synthesizing onchain risk narrative[/cyan]")

    parts = []

    # deployer assessment
    if intel.deployer.suspicious:
        parts.append(
            f"🔴 **CRITICAL — Deployer Risk:** The deployer wallet `{intel.deployer.address}` "
            f"has direct counterparty connections to addresses labeled as exploiters or attackers. "
            f"Treat all admin functions and proxy upgrade paths as potentially compromised."
        )
    else:
        parts.append(
            f"**Deployer Assessment:** Contract deployed {intel.deployer.deploy_date or 'unknown'} "
            f"by `{intel.deployer.address}` ({intel.deployer.tx_count:,} lifetime transactions). "
            f"{'Contract source is verified on Etherscan.' if intel.deployer.is_verified else '⚠ Contract source is NOT verified.'} "
            f"No exploit-connected counterparties detected."
        )

    # economic surface
    if intel.tvl.tvl_current > 0:
        if intel.tvl.tvl_7d_change_pct < -20:
            tvl_note = (
                f"🔴 TVL dropped {intel.tvl.tvl_7d_change_pct:.1f}% in 7 days — "
                f"silent drain is a known post-exploit pattern."
            )
        elif intel.tvl.tvl_7d_change_pct < -10:
            tvl_note = f"⚠ TVL declining {intel.tvl.tvl_7d_change_pct:.1f}% in 7 days."
        else:
            tvl_note = f"TVL stable ({intel.tvl.tvl_7d_change_pct:+.1f}% 7d)."

        parts.append(
            f"**Economic Surface:** {intel.tvl.category or 'Unknown'} protocol "
            f"with ${intel.tvl.tvl_current:,.0f} TVL. {tvl_note}"
        )
    else:
        parts.append(
            f"**Economic Surface:** Protocol not found on DeFiLlama — new, unlisted, or private. "
            f"No independent TVL baseline available. Increases audit risk."
        )

    # smart money
    direction = intel.token_signals.smart_money_direction
    if direction == "exiting":
        parts.append(
            f"🔴 **Smart Money — EXIT:** ${abs(intel.token_signals.net_flow_usd):,.0f} "
            f"net outflow from labeled smart money. Pre-exploit exit pattern. Escalate priority."
        )
    elif direction == "accumulating":
        parts.append(
            f"🟢 **Smart Money — ACCUMULATING:** ${intel.token_signals.net_flow_usd:,.0f} "
            f"net inflow. Growing institutional interest increases attack incentive."
        )
    elif direction == "neutral":
        parts.append(f"🟡 **Smart Money — NEUTRAL:** No significant directional flow.")
    else:
        parts.append(
            f"**Smart Money:** No token data — contract may be a vault not a tradeable token. "
            f"Run TGM against the protocol native token address directly."
        )

    # fresh wallets
    if intel.token_signals.fresh_wallet_accumulation:
        parts.append(
            f"⚠ **Fresh Wallet Accumulation:** Multiple fresh wallets accumulating positions. "
            f"Associated with sybil attacks and attacker staging. Prioritize MEV vectors."
        )

    # suspicious holders
    if intel.token_signals.suspicious_holders:
        holders_list = "\n".join(f"- `{h}`" for h in intel.token_signals.suspicious_holders)
        parts.append(
            f"🔴 **Suspicious Holders:** Exploit-labeled addresses hold positions:\n{holders_list}"
        )

    # historical hacks
    if intel.related_hacks:
        hack_names = ", ".join(h.protocol for h in intel.related_hacks[:3])
        vuln_types = list(set(h.vuln_type for h in intel.related_hacks if h.vuln_type))
        parts.append(
            f"**Historical Patterns:** {len(intel.related_hacks)} prior hacks in "
            f"{intel.tvl.category} category ({hack_names}). "
            f"Recurring vulns: {', '.join(vuln_types[:4]) if vuln_types else 'various'}."
        )

    # audit priority
    if intel.recommended_threat_classes and intel.recommended_threat_classes[0] != "unknown — manual review required":
        parts.append(
            f"**Audit Priority:** {', '.join(f'`{t}`' for t in intel.recommended_threat_classes)}. "
            f"Feed into PrePosv for targeted question generation."
        )

    narrative = "\n\n".join(parts)
    console.print(f"[green]  ✓ narrative complete ({len(narrative)} chars)[/green]")
    return narrative


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

    # step 1 — contract identity
    intel.deployer = await get_contract_identity(contract_address, chain)

    # step 2 — protocol TVL
    intel.tvl = await get_protocol_tvl(contract_address)

    # step 3 — related hacks
    intel.related_hacks = await get_related_hacks(
        intel.tvl.category,
        intel.tvl.protocol_name,
    )

    # step 4 — deployer intelligence
    deployer_data = await get_deployer_intelligence(intel.deployer.address, tracker)
    intel.deployer.labels = deployer_data.get("labels", [])
    intel.deployer.related_wallets = deployer_data.get("related_wallets", [])
    intel.deployer.counterparties = [
        c.get("address", "") for c in deployer_data.get("counterparties", [])
    ]
    intel.deployer.suspicious = deployer_data.get("suspicious", False)

    # step 5 — token signals
    intel.token_signals = await get_token_signals(contract_address, chain, tracker)

    # step 6 — smart money flows
    sm_data = await get_smart_money_flows(contract_address, chain, tracker)

    # step 7 — narrative synthesis
    intel.agent_narrative = await synthesize_with_claude(intel, deployer_data, sm_data)

    # step 8 — derive threat classes
    intel.recommended_threat_classes = _derive_threat_classes(intel, deployer_data)

    intel.credit_log = tracker.log

    console.print(f"\n[bold green]✓ Phase 1 complete — {tracker.spent} credits used[/bold green]\n")
    return intel


def _derive_threat_classes(intel: OnchainIntel, deployer_data: dict) -> list[str]:
    classes = []

    if intel.tvl.tvl_7d_change_pct < -10:
        classes.append("fund_drainage")

    if intel.token_signals.smart_money_direction == "exiting":
        classes.append("oracle_manipulation")
        classes.append("flash_loan")

    if intel.token_signals.suspicious_holders or intel.deployer.suspicious:
        classes.append("access_control")

    if intel.token_signals.fresh_wallet_accumulation:
        classes.append("MEV_liquidation")

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

    if intel.tvl.category.lower() in ["yield aggregator", "lending", "cdp"]:
        if "accounting_drift" not in classes:
            classes.append("accounting_drift")

    return classes if classes else ["unknown — manual review required"]


def render_onchain_intel(intel: OnchainIntel, tracker: CreditTracker) -> str:
    lines = []
    lines.append(f"# TUSCA Onchain Intelligence Brief")
    lines.append(f"> Target: `{intel.contract_address}` | Chain: {intel.chain} | {intel.timestamp}\n")
    lines.append("---\n")

    lines.append("## 1. Protocol Identity\n")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    lines.append(f"| Contract | `{intel.contract_address}` |")
    lines.append(f"| Name | {intel.deployer.contract_name or 'unknown'} |")
    lines.append(f"| Deployer | `{intel.deployer.address}` |")
    lines.append(f"| Deployed | {intel.deployer.deploy_date or 'unknown'} |")
    lines.append(f"| Verified | {'✓ yes' if intel.deployer.is_verified else '✗ no'} |")
    lines.append(f"| Deployer Tx Count | {intel.deployer.tx_count:,} |")
    lines.append("")

    lines.append("## 2. Economic Surface\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Protocol | {intel.tvl.protocol_name or 'not found on DeFiLlama'} |")
    lines.append(f"| Category | {intel.tvl.category or 'unknown'} |")
    lines.append(f"| TVL Current | ${intel.tvl.tvl_current:,.0f} |")
    lines.append(f"| TVL 7d Change | {intel.tvl.tvl_7d_change_pct:+.2f}% |")
    lines.append(f"| TVL 30d Change | {intel.tvl.tvl_30d_change_pct:+.2f}% |")
    if intel.tvl.tvl_7d_change_pct < -10:
        lines.append(f"\n> ⚠ **Risk flag:** TVL declining {intel.tvl.tvl_7d_change_pct:.1f}% in 7 days.")
    lines.append("")

    lines.append("## 3. Historical Hack Patterns\n")
    if intel.related_hacks:
        lines.append(f"Found {len(intel.related_hacks)} related hacks in category '{intel.tvl.category}':\n")
        lines.append("| Protocol | Date | Amount Lost | Vulnerability |")
        lines.append("|----------|------|-------------|---------------|")
        for h in intel.related_hacks:
            lines.append(f"| {h.protocol} | {h.date} | ${h.amount_usd:,.0f} | {h.vuln_type} |")
    else:
        lines.append("No related hacks found for this category.")
    lines.append("")

    lines.append("## 4. Deployer Trust Signals\n")
    trust_flag = "🔴 SUSPICIOUS" if intel.deployer.suspicious else "🟢 CLEAN"
    lines.append(f"**Verdict: {trust_flag}**\n")
    if intel.deployer.related_wallets:
        lines.append(f"- Related wallets: {len(intel.deployer.related_wallets)}")
        for w in intel.deployer.related_wallets[:5]:
            lines.append(f"  - `{w}`")
    if intel.deployer.suspicious:
        lines.append(f"\n> ⚠ Deployer counterparties include exploit-labeled addresses.")
    lines.append("")

    lines.append("## 5. Smart Money Behavior\n")
    direction_emoji = {"accumulating": "🟢", "exiting": "🔴", "neutral": "🟡"}.get(
        intel.token_signals.smart_money_direction, "⚪"
    )
    lines.append("| Signal | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Direction | {direction_emoji} {intel.token_signals.smart_money_direction or 'no data'} |")
    lines.append(f"| Net Flow USD | ${intel.token_signals.net_flow_usd:,.0f} |")
    lines.append(f"| Fresh Wallet Accumulation | {'⚠ yes' if intel.token_signals.fresh_wallet_accumulation else 'no'} |")
    lines.append(f"| Notable Holders | {len(intel.token_signals.notable_holders)} |")
    lines.append(f"| Suspicious Holders | {len(intel.token_signals.suspicious_holders)} |")
    if intel.token_signals.suspicious_holders:
        lines.append(f"\n**Suspicious holders:**")
        for h in intel.token_signals.suspicious_holders:
            lines.append(f"- `{h}`")
    if intel.token_signals.smart_money_direction == "exiting":
        lines.append(f"\n> ⚠ **Risk flag:** Smart money is exiting.")
    lines.append("")

    lines.append("## 6. Onchain Risk Narrative\n")
    lines.append(intel.agent_narrative or "_Narrative unavailable._")
    lines.append("")

    lines.append("## 7. Recommended Threat Classes\n")
    lines.append("Derived from onchain signals — feed into PrePosv:\n")
    for i, tc in enumerate(intel.recommended_threat_classes, 1):
        lines.append(f"{i}. `{tc}`")
    lines.append("")

    lines.append("---\n")
    lines.append(tracker.summary())

    return "\n".join(lines)