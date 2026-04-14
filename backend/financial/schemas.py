"""
PLANN Financial Engine — Pydantic Schemas

All MongoDB collection schemas for the financial system.
Money fields use int (minor units: kuruş for TRY, pence for GBP).
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
import uuid


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Enums as string literals (kept simple for MongoDB compatibility)
# ---------------------------------------------------------------------------

BASE_CURRENCIES = {"GBP", "TRY"}
PAYOUT_MODES = {"manual", "auto"}
PAYOUT_TIERS = {"fast", "standard", "vip"}
FEE_PREFERENCES = {"seller_pays", "buyer_pays"}
PAYMENT_RULES = {"on_site", "deposit", "full_online"}
DEPOSIT_TYPES = {"fixed", "percentage"}

TRANSACTION_TYPES = {
    "payment", "fee", "payout", "refund",
    "dispute_freeze", "dispute_release",
}

TRANSACTION_STATES = {
    "pending", "authorized", "captured", "async_failed",
    "settled", "available",
    "reserved", "paid_out",
    "frozen", "disputed", "resolved_won", "resolved_lost",
    "refunded", "canceled", "failed",
}

PAYOUT_BATCH_STATUSES = {
    "draft", "quoting", "quoted", "funding",
    "processing", "completed", "partial_failure", "failed",
}

PAYOUT_PROVIDERS = {"wise"}
PAYOUT_RAILS = {"bacs", "faster_payments", "swift", "local_tr"}

BATCH_ITEM_STATUSES = {
    "pending", "quoted", "funded",
    "completed", "failed", "cancelled",
}

WEBHOOK_SOURCES = {"stripe_merchant", "stripe_saas", "wise"}
WEBHOOK_PROCESSING_STATUSES = {
    "received", "processing", "processed", "failed", "skipped",
}

QUOTE_STATUSES = {"active", "used", "expired", "cancelled"}

SESSION_CREDIT_STATUSES = {"active", "exhausted", "expired", "refunded"}


# ---------------------------------------------------------------------------
# 1a. Settings Extension (Merchant Payout Settings)
# These fields are ADDED to the existing Settings model in server.py
# ---------------------------------------------------------------------------

class MerchantPayoutSettings(BaseModel):
    """Fields to be added to the existing db.settings documents."""
    model_config = ConfigDict(extra="ignore")

    base_currency: str = "TRY"
    payout_mode: str = "manual"
    payout_tier: str = "standard"
    fee_preference: str = "buyer_pays"

    iban: Optional[str] = None
    account_holder_name: Optional[str] = None
    sort_code: Optional[str] = None
    account_number: Optional[str] = None

    wise_recipient_id: Optional[str] = None
    wise_recipient_verified: bool = False
    wise_recipient_schema_hash: Optional[str] = None

    refund_window_hours: int = 12
    dispute_reserve_rate: int = 500
    kyc_verified: bool = False

    iban_changed_at: Optional[str] = None


class MerchantPayoutSettingsUpdate(BaseModel):
    """Allowed fields for merchant payment settings update."""
    model_config = ConfigDict(extra="ignore")

    payout_mode: Optional[str] = None
    payout_tier: Optional[str] = None
    fee_preference: Optional[str] = None
    iban: Optional[str] = None
    account_holder_name: Optional[str] = None
    sort_code: Optional[str] = None
    account_number: Optional[str] = None
    refund_window_hours: Optional[int] = None


# ---------------------------------------------------------------------------
# 1b. Service Extension
# ---------------------------------------------------------------------------

class ServicePaymentFields(BaseModel):
    """Fields to be added to existing db.services documents."""
    model_config = ConfigDict(extra="ignore")

    payment_rule: str = "on_site"
    deposit_type: Optional[str] = None
    deposit_value: Optional[int] = None


# ---------------------------------------------------------------------------
# 1c. Merchant Wallets
# ---------------------------------------------------------------------------

class MerchantWallet(BaseModel):
    """Virtual wallet for each merchant organization."""
    model_config = ConfigDict(extra="ignore")

    organization_id: str
    base_currency: str = "TRY"

    pending_balance_minor: int = 0
    settled_balance_minor: int = 0
    available_balance_minor: int = 0
    reserved_balance_minor: int = 0
    frozen_balance_minor: int = 0
    refund_reserve_minor: int = 0

    pool_balance_gbp_minor: int = 0

    total_earned_minor: int = 0
    total_paid_out_minor: int = 0
    total_fees_minor: int = 0

    updated_at: str = Field(default_factory=_utcnow)

    @property
    def effective_available_minor(self) -> int:
        """Available balance minus refund reserve — actual payout-eligible amount."""
        return max(0, self.available_balance_minor - self.refund_reserve_minor)


# ---------------------------------------------------------------------------
# 1d. Merchant Transactions (Double-Entry Ledger + State Machine)
# ---------------------------------------------------------------------------

class StateHistoryEntry(BaseModel):
    state: str
    timestamp: str = Field(default_factory=_utcnow)
    trigger: str = ""


class MerchantTransaction(BaseModel):
    """Double-entry ledger record with state machine."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=_uuid)
    organization_id: str
    base_currency: str
    appointment_id: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_name: Optional[str] = None

    type: str
    state: str = "pending"
    state_history: List[Dict[str, Any]] = Field(default_factory=lambda: [])

    amount_display_minor: int = 0
    amount_settled_gbp_minor: Optional[int] = None

    fee_amount_minor: int = 0
    fee_rate_bps: int = 0
    fee_preference: str = "seller_pays"

    exchange_rate_at_time: int = 1_000_000

    stripe_payment_intent_id: Optional[str] = None
    stripe_charge_id: Optional[str] = None
    stripe_checkout_session_id: Optional[str] = None
    stripe_refund_id: Optional[str] = None
    stripe_dispute_id: Optional[str] = None

    wise_transfer_id: Optional[str] = None
    wise_quote_id: Optional[str] = None
    payout_batch_id: Optional[str] = None

    created_at: str = Field(default_factory=_utcnow)
    updated_at: str = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# 1e. Payout Batches
# ---------------------------------------------------------------------------

class PayoutBatchItem(BaseModel):
    organization_id: str
    base_currency: str
    amount_display_minor: int = 0
    amount_gbp_minor: int = 0
    wise_transfer_id: Optional[str] = None
    wise_quote_id: Optional[str] = None
    wise_recipient_id: str = ""
    customer_transaction_id: str = Field(default_factory=_uuid)
    item_status: str = "pending"
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    attempt_count: int = 0


class PayoutBatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=_uuid)
    payout_market: str
    payout_provider: str = "wise"
    payout_rail: str
    chunk_index: int = 0
    chunk_total: int = 1
    status: str = "draft"

    wise_batch_group_id: Optional[str] = None
    wise_batch_group_version: Optional[int] = None

    items: List[Dict[str, Any]] = Field(default_factory=list)

    total_gbp_minor: int = 0

    triggered_by: str = "manual"
    triggered_by_user: Optional[str] = None

    created_at: str = Field(default_factory=_utcnow)
    completed_at: Optional[str] = None


# ---------------------------------------------------------------------------
# 1f. Exchange Rates
# ---------------------------------------------------------------------------

class TryTierLimits(BaseModel):
    fast: int = 600_000
    standard: int = 1_200_000
    vip: int = 3_000_000


class TryTierTargetsGbp(BaseModel):
    fast: int = 10_000
    standard: int = 20_000
    vip: int = 50_000


class ExchangeRate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=_uuid)
    pair: str = "GBP_TRY"
    rate_micro: int = 0
    source: str = "wise_rate"

    try_tier_limits_minor: Dict[str, int] = Field(
        default_factory=lambda: {"fast": 600_000, "standard": 1_200_000, "vip": 3_000_000}
    )
    try_tier_targets_gbp_minor: Dict[str, int] = Field(
        default_factory=lambda: {"fast": 10_000, "standard": 20_000, "vip": 50_000}
    )

    fetched_at: str = Field(default_factory=_utcnow)
    is_current: bool = True


# ---------------------------------------------------------------------------
# 1g. Webhook Events (Event Store)
# ---------------------------------------------------------------------------

class WebhookEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=_uuid)
    source: str
    event_id: str
    event_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    raw_body: str = ""
    raw_headers: Dict[str, str] = Field(default_factory=dict)
    body_sha256: str = ""
    signature_verified: bool = False

    processing_status: str = "received"
    processing_error: Optional[str] = None
    attempt_count: int = 0
    last_attempt_at: Optional[str] = None

    organization_id: Optional[str] = None
    transaction_id: Optional[str] = None

    received_at: str = Field(default_factory=_utcnow)
    processed_at: Optional[str] = None


# ---------------------------------------------------------------------------
# 1h. Wise Quotes
# ---------------------------------------------------------------------------

class WiseQuote(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=_uuid)
    organization_id: str = ""
    payout_batch_id: Optional[str] = None

    wise_quote_id: str = ""
    source_currency: str = "GBP"
    target_currency: str = "TRY"
    source_amount_minor: int = 0
    target_amount_minor: int = 0
    rate_micro: int = 0
    wise_fee_minor: int = 0

    quote_locked_at: str = Field(default_factory=_utcnow)
    quote_expires_at: str = ""

    status: str = "active"
    created_at: str = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# 1i. Session Credits
# ---------------------------------------------------------------------------

class SessionCredit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=_uuid)
    organization_id: str
    customer_phone: str
    service_id: str
    service_name: str = ""
    total_sessions: int
    used_sessions: int = 0
    remaining_sessions: int = 0
    payment_transaction_id: str = ""
    stripe_payment_intent_id: str = ""
    status: str = "active"
    expires_at: Optional[str] = None
    created_at: str = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# 1j. Financial Audit Logs
# ---------------------------------------------------------------------------

class FinancialAuditLog(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=_uuid)
    organization_id: str
    actor: str
    actor_role: str = "admin"
    action: str
    details: Dict[str, Any] = Field(default_factory=dict)
    ip_address: Optional[str] = None
    created_at: str = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# API Response Models
# ---------------------------------------------------------------------------

class WalletResponse(BaseModel):
    """Merchant-facing wallet response — base_currency only, no GBP leak."""
    base_currency: str
    currency_symbol: str
    available: int
    pending: int
    frozen: int
    refund_reserve: int
    effective_available: int
    total_earned: int
    total_paid_out: int
    total_fees: int
    tier: str
    tier_limit: int
    tier_fee_rate_bps: int
    progress_pct: float
    payout_enabled: bool
    payout_enabled_reasons: List[str] = Field(default_factory=list)


class TransactionListItem(BaseModel):
    """Single transaction in merchant's transaction history."""
    id: str
    type: str
    state: str
    amount_display: str
    amount_minor: int
    fee_display: str
    fee_minor: int
    base_currency: str
    created_at: str
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None


class PayoutHistoryItem(BaseModel):
    """Single payout batch in merchant's payout history."""
    id: str
    status: str
    total_display: str
    total_minor: int
    payout_rail: str
    triggered_by: str
    created_at: str
    completed_at: Optional[str] = None


class SuperAdminOverview(BaseModel):
    """SuperAdmin consolidated financial overview."""
    total_pool_gbp_minor: int
    total_pool_gbp_display: str
    total_pool_try_minor: int = 0
    total_pool_try_display: str = "₺0.00"
    gbp_merchant_count: int
    try_merchant_count: int
    gbp_available_total_minor: int
    try_available_total_minor: int
    pending_payouts_count: int
    active_disputes_count: int
    current_gbp_try_rate_micro: int
    current_gbp_try_rate_display: str
    current_rate_display: str = "N/A"


# ---------------------------------------------------------------------------
# MongoDB Index Definitions
# ---------------------------------------------------------------------------

FINANCIAL_INDEXES = {
    "merchant_wallets": [
        {"keys": [("organization_id", 1)], "unique": True},
    ],
    "merchant_transactions": [
        {"keys": [("organization_id", 1), ("created_at", -1)]},
        {"keys": [("stripe_payment_intent_id", 1)], "unique": True, "sparse": True},
        {"keys": [("state", 1)]},
        {"keys": [("payout_batch_id", 1)], "sparse": True},
        {"keys": [("organization_id", 1), ("state", 1)]},
    ],
    "payout_batches": [
        {"keys": [("status", 1)]},
        {"keys": [("payout_market", 1), ("status", 1)]},
        {"keys": [("created_at", -1)]},
    ],
    "exchange_rates": [
        {"keys": [("is_current", 1)]},
        {"keys": [("pair", 1), ("fetched_at", -1)]},
    ],
    "webhook_events": [
        {"keys": [("event_id", 1)], "unique": True},
        {"keys": [("processing_status", 1)]},
        {"keys": [("received_at", -1)]},
    ],
    "wise_quotes": [
        {"keys": [("wise_quote_id", 1)], "unique": True, "sparse": True},
        {"keys": [("status", 1)]},
        {"keys": [("quote_expires_at", 1)]},
    ],
    "session_credits": [
        {"keys": [("organization_id", 1), ("customer_phone", 1), ("service_id", 1)]},
        {"keys": [("status", 1)]},
    ],
    "financial_audit_logs": [
        {"keys": [("organization_id", 1), ("created_at", -1)]},
        {"keys": [("action", 1)]},
    ],
}
