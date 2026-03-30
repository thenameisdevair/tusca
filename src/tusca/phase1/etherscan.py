import httpx
from rich.console import Console
from tusca.utils.config import config
from tusca.models.intel import DeployerIntel

console = Console()


async def get_contract_identity(address: str, chain: str = "ethereum") -> DeployerIntel:
    """Fetch contract identity and deployer info from Etherscan."""
    console.print(f"[cyan]→ Etherscan: fetching contract identity for {address}[/cyan]")

    base_url = _get_base_url(chain)
    deployer = DeployerIntel(address=address)

    async with httpx.AsyncClient(timeout=30) as client:
        # check if contract is verified
        abi_resp = await client.get(base_url, params={
            "module": "contract",
            "action": "getabi",
            "address": address,
            "apikey": config.ETHERSCAN_API_KEY,
        })
        abi_data = abi_resp.json()
        deployer.is_verified = abi_data.get("status") == "1"

        # get contract creation info (deployer + deploy tx)
        creation_resp = await client.get(base_url, params={
            "module": "contract",
            "action": "getcontractcreation",
            "contractaddresses": address,
            "apikey": config.ETHERSCAN_API_KEY,
        })
        creation_data = creation_resp.json()

        if creation_data.get("status") == "1" and creation_data.get("result"):
            result = creation_data["result"][0]
            deployer.address = result.get("contractCreator", address)
            deploy_tx = result.get("txHash", "")

            # get deploy tx timestamp
            if deploy_tx:
                tx_resp = await client.get(base_url, params={
                    "module": "proxy",
                    "action": "eth_getTransactionByHash",
                    "txhash": deploy_tx,
                    "apikey": config.ETHERSCAN_API_KEY,
                })
                tx_data = tx_resp.json()
                block_number = tx_data.get("result", {}).get("blockNumber", "")

                if block_number:
                    block_resp = await client.get(base_url, params={
                        "module": "proxy",
                        "action": "eth_getBlockByNumber",
                        "tag": block_number,
                        "boolean": "false",
                        "apikey": config.ETHERSCAN_API_KEY,
                    })
                    block_data = block_resp.json()
                    timestamp_hex = block_data.get("result", {}).get("timestamp", "0x0")
                    timestamp_int = int(timestamp_hex, 16)
                    from datetime import datetime, timezone
                    deployer.deploy_date = datetime.fromtimestamp(
                        timestamp_int, tz=timezone.utc
                    ).strftime("%Y-%m-%d")

        # get deployer tx count
        tx_count_resp = await client.get(base_url, params={
            "module": "proxy",
            "action": "eth_getTransactionCount",
            "address": deployer.address,
            "tag": "latest",
            "apikey": config.ETHERSCAN_API_KEY,
        })
        tx_count_data = tx_count_resp.json()
        tx_count_hex = tx_count_data.get("result", "0x0")
        deployer.tx_count = int(tx_count_hex, 16)

        # get source code / contract name
        source_resp = await client.get(base_url, params={
            "module": "contract",
            "action": "getsourcecode",
            "address": address,
            "apikey": config.ETHERSCAN_API_KEY,
        })
        source_data = source_resp.json()
        if source_data.get("status") == "1" and source_data.get("result"):
            deployer.contract_name = source_data["result"][0].get("ContractName", "")

    console.print(f"[green]  ✓ deployer: {deployer.address} | verified: {deployer.is_verified} | deployed: {deployer.deploy_date}[/green]")
    return deployer


def _get_base_url(chain: str) -> str:
    urls = {
        "ethereum": "https://api.etherscan.io/api",
        "arbitrum": "https://api.arbiscan.io/api",
        "optimism": "https://api-optimistic.etherscan.io/api",
        "base": "https://api.basescan.org/api",
        "polygon": "https://api.polygonscan.com/api",
    }
    return urls.get(chain.lower(), urls["ethereum"])