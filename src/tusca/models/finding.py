from dataclasses import dataclass, field
from enum import Enum


class VulnClass(str, Enum):
    ORACLE_MANIPULATION = "oracle_manipulation"
    ACCESS_CONTROL = "access_control"
    REENTRANCY = "reentrancy"
    FLASH_LOAN = "flash_loan"
    MEV_LIQUIDATION = "MEV_liquidation"
    ACCOUNTING_DRIFT = "accounting_drift"
    FUND_DRAINAGE = "fund_drainage"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class PrecursorVerdict(str, Enum):
    CLEAN = "CLEAN"
    PROBED = "PROBED"
    STAGED = "STAGED"
    EXPLOITED = "EXPLOITED"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass
class Finding:
    finding_id: str
    severity: Severity
    vuln_class: VulnClass
    affected_function: str
    description: str
    raw_text: str = ""


@dataclass
class SuspiciousTx:
    tx_hash: str
    sender: str
    timestamp: str
    success: bool
    decoded_function: str = ""
    decoded_params: str = ""
    simulation_result: str = ""
    sender_labels: list[str] = field(default_factory=list)


@dataclass
class PrecursorReport:
    contract_address: str
    chain: str
    timestamp: str
    finding: Finding = None
    suspicious_txs: list[SuspiciousTx] = field(default_factory=list)
    flagged_senders: list[dict] = field(default_factory=list)
    capital_staging_signals: list[str] = field(default_factory=list)
    flow_anomalies: list[str] = field(default_factory=list)
    simulation_results: list[dict] = field(default_factory=list)
    agent_analysis: str = ""
    verdict: PrecursorVerdict = PrecursorVerdict.INCONCLUSIVE
    confidence: str = "LOW"
    recommended_action: str = ""
    credit_log: list[dict] = field(default_factory=list)