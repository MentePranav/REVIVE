"""
Configuration models and loader for the REVIVE payment simulator.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any
import yaml

from simulator.enums import CustomerProfile, PaymentMethod, PaymentStatus, FailureCategory


@dataclass
class SimulatorConfig:
    transaction_count: int = 10000
    customer_count: int = 2000
    random_seed: int = 42
    currency: str = "INR"
    start_date: str = "2026-01-01T00:00:00Z"
    simulation_days: int = 90

    # Profile proportions
    profile_proportions: Dict[str, float] = field(default_factory=lambda: {
        CustomerProfile.RELIABLE.value: 0.35,
        CustomerProfile.OCCASIONAL_FAILURE.value: 0.25,
        CustomerProfile.HIGH_FAILURE.value: 0.10,
        CustomerProfile.NEW_CUSTOMER.value: 0.10,
        CustomerProfile.SUBSCRIPTION.value: 0.12,
        CustomerProfile.HIGH_VALUE.value: 0.08,
    })

    # Payment method proportions
    payment_method_proportions: Dict[str, float] = field(default_factory=lambda: {
        PaymentMethod.UPI.value: 0.55,
        PaymentMethod.CARD.value: 0.25,
        PaymentMethod.NETBANKING.value: 0.12,
        PaymentMethod.WALLET.value: 0.08,
    })

    # Target status breakdown
    status_targets: Dict[str, float] = field(default_factory=lambda: {
        PaymentStatus.SUCCESS.value: 0.80,
        PaymentStatus.FAILED.value: 0.14,
        PaymentStatus.ABANDONED.value: 0.06,
    })

    # Failure category distribution
    failure_weights: Dict[str, float] = field(default_factory=lambda: {
        FailureCategory.TRANSIENT_GATEWAY_FAILURE.value: 0.28,
        FailureCategory.BANK_DECLINE.value: 0.22,
        FailureCategory.INSUFFICIENT_FUNDS.value: 0.20,
        FailureCategory.AUTHENTICATION_FAILURE.value: 0.14,
        FailureCategory.PAYMENT_METHOD_FAILURE.value: 0.08,
        FailureCategory.HARD_FAILURE.value: 0.05,
        FailureCategory.HIGH_RISK.value: 0.03,
    })

    @classmethod
    def from_yaml(cls, yaml_path: Path | str | None = None) -> "SimulatorConfig":
        """Loads configuration from YAML with fallback to defaults."""
        if yaml_path is None:
            yaml_path = Path(__file__).parent / "config.yaml"
        else:
            yaml_path = Path(yaml_path)

        if not yaml_path.exists():
            return cls()

        with open(yaml_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        sim_raw = raw.get("simulation", {})
        return cls(
            transaction_count=sim_raw.get("default_transactions", 10000),
            customer_count=sim_raw.get("default_customers", 2000),
            random_seed=sim_raw.get("default_seed", 42),
            currency=sim_raw.get("currency", "INR"),
            start_date=sim_raw.get("start_date", "2026-01-01T00:00:00Z"),
            simulation_days=sim_raw.get("simulation_days", 90),
            profile_proportions=raw.get("customer_profiles", {}).get("proportions", cls().profile_proportions),
            payment_method_proportions=raw.get("payment_methods", {}).get("proportions", cls().payment_method_proportions),
            status_targets=raw.get("status_targets", cls().status_targets),
            failure_weights=raw.get("failure_categories", {}).get("weights", cls().failure_weights),
        )
