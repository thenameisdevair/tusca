from dataclasses import dataclass, field


@dataclass
class DeployerIntel:
    address: str
    deploy_date: str = ""
    contract_name: str = ""
    is_verified: bool = False
    tx_count: int = 0
    labels: list[str] = field(default_factory=list)
    related_wallets: list[str] = field(default_factory=list)
    counterparties: list[str] = field(default_factory=list)
    suspicious: bool = False


@dataclass
class TVLIntel:
    protocol_name: str = ""
    tvl_current: float = 0.0
    tvl_7d_change_pct: float = 0.0
    tvl_30d_change_pct: float = 0.0
    category: str = ""
    chain: str = ""


@dataclass
class HackRecord:
    protocol: str
    date: str
    amount_usd: float
    vuln_type: str
    technique: str


@dataclass
class TokenSignals:
    symbol: str = ""
    market_cap: float = 0.0
    smart_money_direction: str = ""  # accumulating | exiting | neutral
    net_flow_usd: float = 0.0
    notable_holders: list[str] = field(default_factory=list)
    fresh_wallet_accumulation: bool = False
    suspicious_holders: list[str] = field(default_factory=list)


@dataclass
class OnchainIntel:
    contract_address: str
    chain: str
    timestamp: str
    deployer: DeployerIntel = field(default_factory=lambda: DeployerIntel(""))
    tvl: TVLIntel = field(default_factory=TVLIntel)
    related_hacks: list[HackRecord] = field(default_factory=list)
    token_signals: TokenSignals = field(default_factory=TokenSignals)
    agent_narrative: str = ""
    recommended_threat_classes: list[str] = field(default_factory=list)
    credit_log: list[dict] = field(default_factory=list)