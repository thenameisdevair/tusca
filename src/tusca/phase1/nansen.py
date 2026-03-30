import httpx
import json
from eth_account import Account
from x402 import x402Client, x402ClientConfig, SchemeRegistration
from x402.http import x402HTTPClient
from x402.mechanisms.evm.exact import ExactEvmScheme
from x402.mechanisms.evm import EthAccountSigner
from rich.console import Console
from tusca.utils.config import config
from tusca.utils.credits import CreditTracker
from tusca.models.intel import TokenSignals

console = Console()

HEADERS = {
    "apiKey": config.NANSEN_API_KEY,
    "Content-Type": "application/json",
}


def _get_x402_client():
    """Build x402 payment client from wallet private key."""
    account = Account.from_key(config.WALLET_PRIVATE_KEY)
    signer = EthAccountSigner(account)
    payment_client = x402Client.from_config(
        x402ClientConfig(
            schemes=[SchemeRegistration(network="eip155:*", client=ExactEvmScheme(signer))]
        )
    )
    return x402HTTPClient(payment_client)


async def _x402_post(http_client, url: str, body: dict) -> dict:
    """Make an x402-authenticated POST request to Nansen API."""
    transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0")
    async with httpx.AsyncClient(timeout=60, transport=transport) as client:
        response = await client.post(url, json=body)

        if response.status_code == 402:
            payment_headers, _ = await http_client.handle_402_response(
                dict(response.headers),
                response.content,
            )
            response = await client.post(url, json=body, headers=payment_headers)

        if response.status_code == 200:
            return response.json()
        else:
            console.print(f"[yellow]  ⚠ {url} returned {response.status_code}[/yellow]")
            return {}


async def get_deployer_intelligence(
    deployer_address: str,
    tracker: CreditTracker,
) -> dict:
    """Fetch deployer wallet intelligence from Nansen Profiler via x402."""
    console.print(f"[cyan]→ Nansen Profiler: analyzing deployer {deployer_address}[/cyan]")

    result = {
        "balance": {},
        "transactions": [],
        "related_wallets": [],
        "counterparties": [],
        "labels": [],
        "suspicious": False,
    }

    use_x402 = bool(config.WALLET_PRIVATE_KEY)
    x402_client = _get_x402_client() if use_x402 else None
    base = config.NANSEN_BASE_URL

    async def fetch(endpoint: str, body: dict, credit: int) -> dict:
        if use_x402:
            console.print(f"[dim]  ↳ {endpoint} [x402 ~$0.01][/dim]")
            return await _x402_post(x402_client, f"{base}/{endpoint}", body)
        elif tracker.charge(endpoint, credit):
            transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0")
            async with httpx.AsyncClient(
                timeout=30, headers=HEADERS, transport=transport
            ) as client:
                resp = await client.get(f"{base}/{endpoint}", params=body)
                return resp.json() if resp.status_code == 200 else {}
        return {}

    # current balance
    data = await fetch(
        "profiler/address/current-balance",
        {"address": deployer_address, "chain": "ethereum"},
        1,
    )
    result["balance"] = data.get("data", {})

    # transactions
    data = await fetch(
        "profiler/address/transactions",
        {"address": deployer_address, "chain": "ethereum"},
        1,
    )
    result["transactions"] = data.get("data", {}).get("transactions", [])

    # related wallets
    data = await fetch(
        "profiler/address/related-wallets",
        {"address": deployer_address},
        1,
    )
    wallets = data.get("data", {}).get("relatedWallets", [])
    result["related_wallets"] = [w.get("address", "") for w in wallets[:10]]

    # counterparties
    data = await fetch(
        "profiler/address/counterparties",
        {"address": deployer_address, "chain": "ethereum"},
        5,
    )
    parties = data.get("data", {}).get("counterparties", [])
    result["counterparties"] = [
        {
            "address": p.get("address", ""),
            "labels": p.get("labels", []),
            "tx_count": p.get("txCount", 0),
        }
        for p in parties[:10]
    ]
    for p in result["counterparties"]:
        labels_lower = [l.lower() for l in p.get("labels", [])]
        if any(
            word in " ".join(labels_lower)
            for word in ["exploit", "hack", "attack", "phish", "drainer"]
        ):
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
    """Fetch token flow intelligence from Nansen Token God Mode via x402."""
    console.print(f"[cyan]→ Nansen TGM: fetching token signals for {token_address}[/cyan]")

    signals = TokenSignals(symbol="")
    use_x402 = bool(config.WALLET_PRIVATE_KEY)
    x402_client = _get_x402_client() if use_x402 else None
    base = config.NANSEN_BASE_URL

    async def fetch(endpoint: str, body: dict, credit: int) -> dict:
        if use_x402:
            console.print(f"[dim]  ↳ {endpoint} [x402 ~$0.01][/dim]")
            return await _x402_post(x402_client, f"{base}/{endpoint}", body)
        elif tracker.charge(endpoint, credit):
            transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0")
            async with httpx.AsyncClient(
                timeout=30, headers=HEADERS, transport=transport
            ) as client:
                resp = await client.get(f"{base}/{endpoint}", params=body)
                return resp.json() if resp.status_code == 200 else {}
        return {}

    # token information
    data = await fetch(
        "tgm/token-information",
        {"tokenAddress": token_address, "chain": chain},
        1,
    )
    if data:
        d = data.get("data", {})
        signals.symbol = d.get("symbol", "")
        signals.market_cap = float(d.get("marketCap", 0))

    # flow intelligence
    data = await fetch(
        "tgm/flow-intelligence",
        {"tokenAddress": token_address, "chain": chain},
        1,
    )
    if data:
        sm = data.get("data", {}).get("smartMoney", {})
        net = sm.get("netFlow", 0)
        if net > 0:
            signals.smart_money_direction = "accumulating"
        elif net < 0:
            signals.smart_money_direction = "exiting"
        else:
            signals.smart_money_direction = "neutral"
        signals.net_flow_usd = float(net)

    # who bought and sold
    data = await fetch(
        "tgm/who-bought-sold",
        {"tokenAddress": token_address, "chain": chain},
        1,
    )
    if data:
        buyers = data.get("data", {}).get("buyers", [])
        fresh = [b for b in buyers if "fresh" in str(b.get("labels", "")).lower()]
        signals.fresh_wallet_accumulation = len(fresh) > 3

    # top holders
    data = await fetch(
        "tgm/holders",
        {"tokenAddress": token_address, "chain": chain, "limit": 20},
        5,
    )
    if data:
        holders = data.get("data", {}).get("holders", [])
        for h in holders:
            labels = h.get("labels", [])
            address = h.get("address", "")
            labels_lower = [l.lower() for l in labels]
            if any(
                word in " ".join(labels_lower)
                for word in ["exploit", "hack", "attack"]
            ):
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
    """Fetch smart money netflows and recent DEX trades via x402."""
    console.print(f"[cyan]→ Nansen Smart Money: fetching netflows[/cyan]")

    result = {"netflow": {}, "dex_trades": []}
    use_x402 = bool(config.WALLET_PRIVATE_KEY)
    x402_client = _get_x402_client() if use_x402 else None
    base = config.NANSEN_BASE_URL

    async def fetch(endpoint: str, body: dict, credit: int) -> dict:
        if use_x402:
            console.print(f"[dim]  ↳ {endpoint} [x402 ~$0.05][/dim]")
            return await _x402_post(x402_client, f"{base}/{endpoint}", body)
        elif tracker.charge(endpoint, credit):
            transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0")
            async with httpx.AsyncClient(
                timeout=30, headers=HEADERS, transport=transport
            ) as client:
                resp = await client.get(f"{base}/{endpoint}", params=body)
                return resp.json() if resp.status_code == 200 else {}
        return {}

    # netflows
    data = await fetch(
        "smart-money/netflows",
        {"tokenAddress": token_address, "chain": chain},
        5,
    )
    result["netflow"] = data.get("data", {})

    # dex trades
    data = await fetch(
        "smart-money/dex-trades",
        {"tokenAddress": token_address, "chain": chain, "limit": 20},
        5,
    )
    result["dex_trades"] = data.get("data", {}).get("trades", [])

    console.print(
        f"[green]  ✓ smart money fetched | "
        f"recent trades: {len(result['dex_trades'])}[/green]"
    )
    return result