import httpx
from rich.console import Console
from tusca.utils.config import config
from tusca.models.intel import TVLIntel, HackRecord

console = Console()


async def get_protocol_tvl(address: str) -> TVLIntel:
    """Fetch protocol TVL and metadata from DeFiLlama."""
    console.print(f"[cyan]→ DeFiLlama: fetching protocol metadata[/cyan]")

    tvl = TVLIntel()

    async with httpx.AsyncClient(timeout=30) as client:
        # get all protocols and find match by address
        protocols_resp = await client.get(f"{config.DEFILLAMA_BASE_URL}/protocols")
        protocols = protocols_resp.json()

        match = None
        address_lower = address.lower()

        for p in protocols:
            # check address field
            if isinstance(p.get("address"), str):
                if address_lower in p["address"].lower():
                    match = p
                    break
            # check slug/contracts
            chains_data = p.get("chains", [])
            if address_lower in str(p).lower():
                match = p
                break

        if match:
            tvl.protocol_name = match.get("name", "")
            tvl.category = match.get("category", "")
            tvl.chain = match.get("chain", "")
            tvl.tvl_current = match.get("tvl", 0.0)

            # get TVL history for 7d and 30d change
            slug = match.get("slug", "")
            if slug:
                history_resp = await client.get(
                    f"{config.DEFILLAMA_BASE_URL}/protocol/{slug}"
                )
                history_data = history_resp.json()
                tvl_history = history_data.get("tvl", [])

                if len(tvl_history) >= 2:
                    current = tvl_history[-1].get("totalLiquidityUSD", 0)
                    day_7_ago = tvl_history[-7].get("totalLiquidityUSD", 0) if len(tvl_history) >= 7 else current
                    day_30_ago = tvl_history[-30].get("totalLiquidityUSD", 0) if len(tvl_history) >= 30 else current

                    if day_7_ago > 0:
                        tvl.tvl_7d_change_pct = round(((current - day_7_ago) / day_7_ago) * 100, 2)
                    if day_30_ago > 0:
                        tvl.tvl_30d_change_pct = round(((current - day_30_ago) / day_30_ago) * 100, 2)

            console.print(f"[green]  ✓ protocol: {tvl.protocol_name} | TVL: ${tvl.tvl_current:,.0f} | category: {tvl.category}[/green]")
        else:
            console.print(f"[yellow]  ⚠ no DeFiLlama protocol match found for {address}[/yellow]")

    return tvl


async def get_related_hacks(category: str, protocol_name: str) -> list[HackRecord]:
    """Fetch hacks from DeFiLlama filtered by category or protocol name."""
    console.print(f"[cyan]→ DeFiLlama: fetching hack history for category '{category}'[/cyan]")

    hacks = []

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{config.DEFILLAMA_BASE_URL}/hacks")

        if resp.status_code != 200:
            console.print(f"[yellow]  ⚠ DeFiLlama hacks endpoint returned {resp.status_code}[/yellow]")
            return hacks

        all_hacks = resp.json()

        for h in all_hacks:
            hack_category = h.get("category", "").lower()
            hack_name = h.get("name", "").lower()

            category_match = category.lower() in hack_category or hack_category in category.lower()
            name_match = protocol_name.lower() in hack_name if protocol_name else False

            if category_match or name_match:
                hacks.append(HackRecord(
                    protocol=h.get("name", ""),
                    date=h.get("date", ""),
                    amount_usd=float(h.get("funds", 0)),
                    vuln_type=h.get("vulnerability", ""),
                    technique=h.get("technique", h.get("vulnerability", "")),
                ))

        console.print(f"[green]  ✓ found {len(hacks)} related hacks[/green]")

    return hacks[:10]  # cap at 10 most relevant