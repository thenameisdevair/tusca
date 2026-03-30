
import asyncio
import os
import httpx
from eth_account import Account
from x402 import x402Client, x402ClientConfig, SchemeRegistration
from x402.http import x402HTTPClient
from x402.mechanisms.evm.exact import ExactEvmScheme
from x402.mechanisms.evm import EthAccountSigner
from dotenv import load_dotenv

load_dotenv()

async def main():
    account = Account.from_key(os.getenv("EVM_PRIVATE_KEY"))
    signer = EthAccountSigner(account)

    config = x402ClientConfig(
        schemes=[
            SchemeRegistration(network="eip155:*", client=ExactEvmScheme(signer)),
        ],
    )
    payment_client = x402Client.from_config(config)
    http_client = x402HTTPClient(payment_client)

    url = "https://api.nansen.ai/api/v1/profiler/address/current-balance"
    params = {
        "address": "0x439dead08d45811d9ee380e58161baa87f7e8757",
        "chain": "ethereum"
    }

    transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0")
    async with httpx.AsyncClient(timeout=60, transport=transport) as client:
        response = await client.get(url, params=params)
        print(f"Initial status: {response.status_code}")

        if response.status_code == 402:
            print("402 received — handling payment...")
            payment_headers, payload = await http_client.handle_402_response(
                dict(response.headers),
                response.content,
            )
            print(f"Payment headers generated: {list(payment_headers.keys())}")

            # retry with payment headers — use POST
            response = await client.post(
                url,
                params=params,
                headers=payment_headers,
                json={
                    "address": "0x439dead08d45811d9ee380e58161baa87f7e8757",
                    "chain": "ethereum"
                }
            )
            print(f"Retry status: {response.status_code}")
            print(response.json())
        else:
            print(response.json())

asyncio.run(main())