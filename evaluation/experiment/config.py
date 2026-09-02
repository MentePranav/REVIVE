"""
Configuration objects for REVIVE Experimental Evaluation & Holdout Benchmarking.
"""

from typing import List
from pydantic import BaseModel, Field

from policy.config import PolicyConfig


class ExperimentConfig(BaseModel):
    """Centralized configuration for reproducible evaluation experiments."""
    experiment_id: str = "exp_revive_benchmark_001"
    
    # Dataset Seeds
    dev_seed: int = 42
    eval_seeds: List[int] = Field(default_factory=lambda: [101, 202, 303, 404, 505])
    
    # Sample Sizes
    dev_transaction_count: int = 2000
    eval_transaction_count: int = 10000
    
    # Statistical Parameters
    bootstrap_samples: int = 1000
    confidence_level: float = 0.95
    
    # Policy Parameters
    policy_config: PolicyConfig = Field(default_factory=PolicyConfig)
    
    # System Versions
    engine_version: str = "0.4.0"
    policy_version: str = "1.0.0"
    executor_version: str = "1.0.0"
    experiment_version: str = "1.0.0"
