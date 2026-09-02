"""
CLI Tool for Batch Policy Evaluation and Safety Auditing.
Usage:
    python -m policy.cli --input data/revive_analysis/recommendations.jsonl --output data/policy_analysis/
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Ensure UTF-8 stdout across all console environments
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agent.models import ReviveRecommendation
from policy.config import PolicyConfig
from policy.engine import PolicyEngine
from policy.models import (
    PolicyBatchSummary,
    PolicyDecisionType,
    PolicyRuleId,
)
from policy.state_context import CustomerStateContext, PaymentStateContext


def main():
    parser = argparse.ArgumentParser(description="REVIVE Policy, Safety & Governance Batch Evaluator")
    parser.add_argument("--input", "-i", type=str, default="data/revive_analysis/recommendations.jsonl", help="Path to recommendations.jsonl")
    parser.add_argument("--output", "-o", type=str, default="data/policy_analysis", help="Output directory for policy decisions and audit logs")

    args = parser.parse_args()
    in_file = Path(args.input)
    if not in_file.exists():
        print(f"[!] Input file {in_file.resolve()} not found. Generating fresh recommendations first...")
        import subprocess
        subprocess.run([sys.executable, "-m", "agent.cli", "--dataset", "data", "--output", "data/revive_analysis"], check=True)

    print(f"[*] Loading recommendations from {in_file.resolve()}...")
    recommendations = []
    with open(in_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                recommendations.append(ReviveRecommendation.model_validate_json(line))

    print(f"[*] Evaluating {len(recommendations):,} recommendations against Zero-Trust Policy Engine...")

    config = PolicyConfig()
    engine = PolicyEngine(config)

    t0 = time.perf_counter()
    decisions = []
    audit_records = []

    allowed_count = 0
    denied_count = 0
    human_review_count = 0
    no_action_count = 0

    blocked_safety_resolved = 0
    blocked_attempt_cap = 0
    blocked_confidence_gate = 0
    blocked_risk_gate = 0
    blocked_contact_limit = 0
    blocked_cooldown = 0
    blocked_allowlist = 0
    blocked_template = 0

    for rec in recommendations:
        p_state = PaymentStateContext(
            payment_id=rec.payment_id or f"pay_{rec.event_id}",
            customer_id=rec.customer_id
        )
        c_state = CustomerStateContext(customer_id=rec.customer_id)

        decision = engine.evaluate(rec, p_state, c_state)
        decisions.append(decision)

        audit = engine.create_audit_record(decision, rec, attempt_count=0)
        audit_records.append(audit)

        # Accumulate metrics
        if decision.decision == PolicyDecisionType.ALLOW:
            allowed_count += 1
        elif decision.decision == PolicyDecisionType.DENY:
            denied_count += 1
        elif decision.decision == PolicyDecisionType.HUMAN_REVIEW:
            human_review_count += 1
        elif decision.decision == PolicyDecisionType.NO_ACTION:
            no_action_count += 1

        if decision.primary_rule_id == PolicyRuleId.P002_PAYMENT_ALREADY_RESOLVED:
            blocked_safety_resolved += 1
        elif decision.primary_rule_id == PolicyRuleId.P003_MAX_AUTOMATED_ATTEMPTS:
            blocked_attempt_cap += 1
        elif decision.primary_rule_id == PolicyRuleId.P004_LOW_DIAGNOSIS_CONFIDENCE:
            blocked_confidence_gate += 1
        elif decision.primary_rule_id == PolicyRuleId.P005_HIGH_RISK_GATE:
            blocked_risk_gate += 1
        elif decision.primary_rule_id == PolicyRuleId.P007_CUSTOMER_CONTACT_LIMIT:
            blocked_contact_limit += 1
        elif decision.primary_rule_id == PolicyRuleId.P008_COOLDOWN_ACTIVE:
            blocked_cooldown += 1
        elif decision.primary_rule_id == PolicyRuleId.P006_ACTION_NOT_ALLOWLISTED:
            blocked_allowlist += 1
        elif decision.primary_rule_id == PolicyRuleId.P009_UNAPPROVED_TEMPLATE:
            blocked_template += 1

    t1 = time.perf_counter()
    elapsed = t1 - t0
    rate = len(recommendations) / elapsed if elapsed > 0 else 0.0

    n = len(recommendations)
    summary = PolicyBatchSummary(
        total_evaluated=n,
        allowed_count=allowed_count,
        denied_count=denied_count,
        human_review_count=human_review_count,
        no_action_count=no_action_count,
        blocked_by_safety_resolved=blocked_safety_resolved,
        blocked_by_attempt_cap=blocked_attempt_cap,
        blocked_by_confidence_gate=blocked_confidence_gate,
        blocked_by_risk_gate=blocked_risk_gate,
        blocked_by_contact_limit=blocked_contact_limit,
        blocked_by_cooldown=blocked_cooldown,
        blocked_by_allowlist=blocked_allowlist,
        blocked_by_template_safety=blocked_template,
        policy_version=config.policy_version
    )

    # Format Summary Report
    print("\n" + "=" * 70)
    print("            REVIVE POLICY, SAFETY & GOVERNANCE REPORT           ")
    print("=" * 70)
    print(f"Recommendations Evaluated     : {summary.total_evaluated:,}")
    print(f"Policy Engine Version         : {summary.policy_version}")
    print(f"Execution Latency             : {elapsed * 1000:.2f} ms ({rate:,.1f} decisions/sec)")
    print("-" * 70)
    print("POLICY DECISION BREAKDOWN:")
    print(f"  ALLOW (Authorized)          : {summary.allowed_count / n * 100:5.1f}%  ({summary.allowed_count:,})")
    print(f"  HUMAN_REVIEW (Escalated)    : {summary.human_review_count / n * 100:5.1f}%  ({summary.human_review_count:,})")
    print(f"  NO_ACTION (Passive)         : {summary.no_action_count / n * 100:5.1f}%  ({summary.no_action_count:,})")
    print(f"  DENY (Blocked)              : {summary.denied_count / n * 100:5.1f}%  ({summary.denied_count:,})")
    print("-" * 70)
    print("SAFETY & POLICY GATING BREAKDOWN:")
    print(f"  Confidence Gate (< 0.85)    : {summary.blocked_by_confidence_gate:,}")
    print(f"  High-Risk Gate Flagged      : {summary.blocked_by_risk_gate:,}")
    print(f"  Attempt Cap Exceeded        : {summary.blocked_by_attempt_cap:,}")
    print(f"  Payment Already Resolved    : {summary.blocked_by_safety_resolved:,}")
    print(f"  Customer Contact Limit      : {summary.blocked_by_contact_limit:,}")
    print(f"  Cooldown Active             : {summary.blocked_by_cooldown:,}")
    print("=" * 70 + "\n")

    # Write Outputs
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_file = out_dir / "policy_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(summary.model_dump_json(indent=2))

    decisions_file = out_dir / "policy_decisions.jsonl"
    with open(decisions_file, "w", encoding="utf-8") as f:
        for d in decisions:
            f.write(d.model_dump_json() + "\n")

    audit_file = out_dir / "policy_audit_log.jsonl"
    with open(audit_file, "w", encoding="utf-8") as f:
        for a in audit_records:
            f.write(a.model_dump_json() + "\n")

    print(f"[+] Output written to {out_dir.resolve()}")


if __name__ == "__main__":
    main()
