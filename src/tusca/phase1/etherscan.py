import httpx
from datetime import datetime, timezone
from rich.console import Console
from tusca.utils.config import config
from tusca.models.intel import DeployerIntel

console = Console()


def _get_base_url(chain: str) -> str:
    return "https://api.etherscan.io/v2/api"


def _get_chain_id(chain: str) -> int:
    chain_ids = {
        "ethereum": 1,
        "arbitrum": 42161,
        "optimism": 10,
        "base": 8453,
        "polygon": 137,
    }
    return chain_ids.get(chain.lower(), 1)


async def get_contract_identity(address: str, chain: str = "ethereum") -> DeployerIntel:
    """Fetch contract identity and deployer info from Etherscan V2."""
    console.print(f"[cyan]→ Etherscan: fetching contract identity for {address}[/cyan]")

    base_url = _get_base_url(chain)
    chain_id = _get_chain_id(chain)
    deployer = DeployerIntel(address=address)

    async with httpx.AsyncClient(timeout=30) as client:

        # check if contract is verified
        abi_resp = await client.get(base_url, params={
            "chainid": chain_id,
            "module": "contract",
            "action": "getabi",
            "address": address,
            "apikey": config.ETHERSCAN_API_KEY,
        })
        abi_data = abi_resp.json()
        deployer.is_verified = abi_data.get("status") == "1"

        # get contract creation info
        creation_resp = await client.get(base_url, params={
            "chainid": chain_id,
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

            if deploy_tx:
                tx_resp = await client.get(base_url, params={
                    "chainid": chain_id,
                    "module": "proxy",
                    "action": "eth_getTransactionByHash",
                    "txhash": deploy_tx,
                    "apikey": config.ETHERSCAN_API_KEY,
                })
                tx_data = tx_resp.json()
                block_number = tx_data.get("result", {}).get("blockNumber", "")

                if block_number:
                    block_resp = await client.get(base_url, params={
                        "chainid": chain_id,
                        "module": "proxy",
                        "action": "eth_getBlockByNumber",
                        "tag": block_number,
                        "boolean": "false",
                        "apikey": config.ETHERSCAN_API_KEY,
                    })
                    block_data = block_resp.json()
                    timestamp_hex = block_data.get("result", {}).get("timestamp", "0x0")
                    try:
                        timestamp_int = int(timestamp_hex, 16)
                        deployer.deploy_date = datetime.fromtimestamp(
                            timestamp_int, tz=timezone.utc
                        ).strftime("%Y-%m-%d")
                    except (ValueError, TypeError):
                        deployer.deploy_date = "unknown"

        # get deployer tx count
        tx_count_resp = await client.get(base_url, params={
            "chainid": chain_id,
            "module": "proxy",
            "action": "eth_getTransactionCount",
            "address": deployer.address,
            "tag": "latest",
            "apikey": config.ETHERSCAN_API_KEY,
        })
        tx_count_data = tx_count_resp.json()
        tx_count_hex = tx_count_data.get("result", "0x0")
        try:
            deployer.tx_count = int(tx_count_hex, 16)
        except (ValueError, TypeError):
            deployer.tx_count = 0

        # get contract name
        source_resp = await client.get(base_url, params={
            "chainid": chain_id,
            "module": "contract",
            "action": "getsourcecode",
            "address": address,
            "apikey": config.ETHERSCAN_API_KEY,
        })
        source_data = source_resp.json()
        if source_data.get("status") == "1" and source_data.get("result"):
            deployer.contract_name = source_data["result"][0].get("ContractName", "")

    console.print(
        f"[green]  ✓ deployer: {deployer.address} | "
        f"verified: {deployer.is_verified} | "
        f"deployed: {deployer.deploy_date}[/green]"
    )
    return deployer