import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    NANSEN_API_KEY: str = os.getenv("NANSEN_API_KEY", "")
    ETHERSCAN_API_KEY: str = os.getenv("ETHERSCAN_API_KEY", "")
    TENDERLY_ACCESS_KEY: str = os.getenv("TENDERLY_ACCESS_KEY", "")
    TENDERLY_ACCOUNT: str = os.getenv("TENDERLY_ACCOUNT", "")
    TENDERLY_PROJECT: str = os.getenv("TENDERLY_PROJECT", "")
    WALLET_PRIVATE_KEY: str = os.getenv("WALLET_PRIVATE_KEY", "")

    NANSEN_BASE_URL: str = "https://api.nansen.ai/api/v1"
    ETHERSCAN_BASE_URL: str = "https://api.etherscan.io/v2/api"
    DEFILLAMA_BASE_URL: str = "https://api.llama.fi"
    DEFILLAMA_COINS_URL: str = "https://coins.llama.fi"
    FOURBYTE_BASE_URL: str = "https://www.4byte.directory/api/v1"
    TENDERLY_BASE_URL: str = "https://api.tenderly.co/api/v1"

    @classmethod
    def validate(cls) -> list[str]:
        missing = []
        if not cls.NANSEN_API_KEY and not cls.WALLET_PRIVATE_KEY:
            missing.append("NANSEN_API_KEY or WALLET_PRIVATE_KEY")
        if not cls.ETHERSCAN_API_KEY:
            missing.append("ETHERSCAN_API_KEY")
        return missing


config = Config()