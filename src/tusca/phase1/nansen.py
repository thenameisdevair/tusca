import httpx
import json
from rich.console import Console
from tusca.utils.config import config
from tusca.utils.credits import CreditTracker
from tusca.models.intel import TokenSignals

console = Console()

HEADERS = {
    "apiKey": config.NANSEN_API_KEY,
    "Content-Type": "application/json",
}


async def get_deployer_intelligence(
    deployer_address: str,
    tracker: CreditTracker,
) -> dict:
    """Fetch deployer wallet intelligence from Nansen Profiler."""
    console.print(f"[cyan]→ Nansen Profiler: analyzing deployer {deployer_address}[/cyan]")

    result = {
        "balance": {},
        "transactions": [],
        "related_wallets": [],
        "counterparties": [],
        "labels": [],
        "suspicious": False,
    }

    async with httpx.AsyncClient(timeout=30) as client:

        # current balance
        if tracker.charge("profiler/address/current-balance", 1):
            resp = await client.get(
                f"{config.NANSEN_BASE_URL}/profiler/address/current-balance",
                headers=HEADERS,
                params={"address": deployer_address, "chain": "ethereum"},
            )
            if resp.status_code == 200:
                result["balance"] = resp.json().get("data", {})

        # recent transactions
        if tracker.charge("profiler/address/transactions", 1):
            resp = await client.get(
                f"{config.NANSEN_BASE_URL}/profiler/address/transactions",
                headers=HEADERS,
                params={"address": deployer_address, "chain": "ethereum", "limit": 10},
            )
            if resp.status_code == 200:
                result["transactions"] = resp.json().get("data", {}).get("transactions", [])

        # related wallets
        if tracker.charge("profiler/address/related-wallets", 1):
            resp = await client.get(
                f"{config.NANSEN_BASE_URL}/profiler/address/related-wallets",
                headers=HEADERS,
                params={"address": deployer_address},
            )
            if resp.status_code == 200:
                wallets = resp.json().get("data", {}).get("relatedWallets", [])
                result["related_wallets"] = [w.get("address", "") for w in wallets[:10]]

        # counterparties
        if tracker.charge("profiler/address/counterparties", 5):
            resp = await client.get(
                f"{config.NANSEN_BASE_URL}/profiler/address/counterparties",
                headers=HEADERS,
                params={"address": deployer_address, "chain": "ethereum"},
            )
            if resp.status_code == 200:
                parties = resp.json().get("data", {}).get("counterparties", [])
                result["counterparties"] = [
                    {
                        "address": p.get("address", ""),
                        "labels": p.get("labels", []),
                        "tx_count": p.get("txCount", 0),
                    }
                    for p in parties[:10]
                ]
                # flag suspicious if any counterparty has exploit-related labels
                for p in result["counterparties"]:
                    labels_lower = [l.lower() for l in p.get("labels", [])]
                    if any(word in " ".join(labels_lower) for word in ["exploit", "hack", "attack", "phish", "drainer"]):
                        result["suspicious"] = True

    console.print(
        f"[green]  ✓ deployer profiled | suspicious: {result['suspicious']} | "
        f"counterparties: {len(result['counterparties'])}[/green]"
    )
    return result


async def get_token_signals(
    token_address: str,
    chain: str,
    tracker: CreditTracker,
) -> TokenSignals:
    """Fetch token flow intelligence from Nansen Token God Mode."""
    console.print(f"[cyan]→ Nansen TGM: fetching token signals for {token_address}[/cyan]")

    signals = TokenSignals(symbol="")

    async with httpx.AsyncClient(timeout=30) as client:

        # token information
        if tracker.charge("tgm/token-information", 1):
            resp = await client.get(
                f"{config.NANSEN_BASE_URL}/tgm/token-information",
                headers=HEADERS,
                params={"tokenAddress": token_address, "chain": chain},
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                signals.symbol = data.get("symbol", "")
                signals.market_cap = float(data.get("marketCap", 0))

        # flow intelligence
        if tracker.charge("tgm/flow-intelligence", 1):
            resp = await client.get(
                f"{config.NANSEN_BASE_URL}/tgm/flow-intelligence",
                headers=HEADERS,
                params={"tokenAddress": token_address, "chain": chain},
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                smart_money_flow = data.get("smartMoney", {})
                net = smart_money_flow.get("netFlow", 0)
                if net > 0:
                    signals.smart_money_direction = "accumulating"
                elif net < 0:
                    signals.smart_money_direction = "exiting"
                else:
                    signals.smart_money_direction = "neutral"
                signals.net_flow_usd = float(net)

        # who bought and sold
        if tracker.charge("tgm/who-bought-sold", 1):
            resp = await client.get(
                f"{config.NANSEN_BASE_URL}/tgm/who-bought-sold",
                headers=HEADERS,
                params={"tokenAddress": token_address, "chain": chain},
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                buyers = data.get("buyers", [])
                # flag fresh wallets
                fresh = [b for b in buyers if "fresh" in str(b.get("labels", "")).lower()]
                signals.fresh_wallet_accumulation = len(fresh) > 3

        # top holders
        if tracker.charge("tgm/holders", 5):
            resp = await client.get(
                f"{config.NANSEN_BASE_URL}/tgm/holders",
                headers=HEADERS,
                params={"tokenAddress": token_address, "chain": chain, "limit": 20},
            )
            if resp.status_code == 200:
                holders = resp.json().get("data", {}).get("holders", [])
                for h in holders:
                    labels = h.get("labels", [])
                    address = h.get("address", "")
                    labels_lower = [l.lower() for l in labels]
                    if any(word in " ".join(labels_lower) for word in ["exploit", "hack", "attack"]):
                        signals.suspicious_holders.append(f"{address} ({', '.join(labels)})")
                    elif labels:
                        signals.notable_holders.append(f"{address} ({', '.join(labels)})")

    console.print(
        f"[green]  ✓ token: {signals.symbol} | smart money: {signals.smart_money_direction} "
        f"| notable holders: {len(signals.notable_holders)} "
        f"| suspicious: {len(signals.suspicious_holders)}[/green]"
    )
    return signals


async def get_smart_money_flows(
    token_address: str,
    chain: str,
    tracker: CreditTracker,
) -> dict:
    """Fetch smart money netflows and recent DEX trades."""
    console.print(f"[cyan]→ Nansen Smart Money: fetching netflows[/cyan]")

    result = {"netflow": {}, "dex_trades": []}

    async with httpx.AsyncClient(timeout=30) as client:

        # netflows
        if tracker.charge("smart-money/netflows", 5):
            resp = await client.get(
                f"{config.NANSEN_BASE_URL}/smart-money/netflows",
                headers=HEADERS,
                params={"tokenAddress": token_address, "chain": chain},
            )
            if resp.status_code == 200:
                result["netflow"] = resp.json().get("data", {})

        # dex trades
        if tracker.charge("smart-money/dex-trades", 5):
            resp = await client.get(
                f"{config.NANSEN_BASE_URL}/smart-money/dex-trades",
                headers=HEADERS,
                params={"tokenAddress": token_address, "chain": chain, "limit": 20},
            )
            if resp.status_code == 200:
                result["dex_trades"] = resp.json().get("data", {}).get("trades", [])

    console.print(
        f"[green]  ✓ smart money netflow fetched | "
        f"recent trades: {len(result['dex_trades'])}[/green]"
    )
    return result


async def run_agent_fast(
    query: str,
    tracker: CreditTracker,
    conversation_id: str = None,
) -> str:
    """Stream a query to Nansen Agent /fast and return the full response text."""
    console.print(f"[cyan]→ Nansen Agent /fast: synthesizing onchain risk narrative[/cyan]")

    if not tracker.charge("agent/fast", 200):
        return "Agent synthesis skipped — credit budget exceeded."

    full_text = ""
    tool_calls = []

    async with httpx.AsyncClient(timeout=120) as client:
        payload = {"text": query}
        if conversation_id:
            payload["conversation_id"] = conversation_id

        async with client.stream(
            "POST",
            f"{config.NANSEN_BASE_URL}/agent/fast",
            headers=HEADERS,
            json=payload,
        ) as response:
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    break
                try:
                    event = json.loads(raw)
                    etype = event.get("type")
                    if etype == "delta":
                        full_text += event.get("text", "")
                    elif etype == "tool_call":
                        tool_calls.append(event.get("name", ""))
                    elif etype == "error":
                        console.print(f"[red]  ✗ agent error: {event.get('error')}[/red]")
                except json.JSONDecodeError:
                    continue

    if tool_calls:
        console.print(f"[dim]  ↳ agent used tools: {', '.join(set(tool_calls))}[/dim]")
    console.print(f"[green]  ✓ agent narrative complete ({len(full_text)} chars)[/green]")

    return full_text