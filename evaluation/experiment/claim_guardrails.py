"""
Claim Guardrail and Scientific Integrity Validator for REVIVE Phase 7.
Ensures evaluation reports strictly adhere to synthetic benchmark disclaimers and do not make unverified production claims.
"""

import re
from typing import List, Tuple


class ClaimGuardrails:
    """Scans reports and text outputs for ungrounded claims or missing synthetic disclaimers."""

    PROHIBITED_PATTERNS = [
        r"\bguaranteed recovery\b",
        r"\bguaranteed roi\b",
        r"\bactual razorpay internal\b",
        r"\breal production customer\b",
        r"\bproduction fraud performance\b",
        r"\bwill recover inr\b",
        r"\bguarantees \d+% recovery\b",
    ]

    REQUIRED_DISCLAIMER_KEYWORDS = [
        "synthetic",
        "simulation",
        "benchmark",
    ]

    @classmethod
    def validate_report(cls, report_text: str) -> Tuple[bool, List[str]]:
        """
        Validates that report text contains necessary synthetic disclaimers and zero prohibited claims.
        Returns: (is_valid, violation_list)
        """
        violations: List[str] = []
        lower_text = report_text.lower()

        # 1. Check for prohibited patterns
        for pattern in cls.PROHIBITED_PATTERNS:
            matches = re.findall(pattern, lower_text)
            if matches:
                violations.append(f"Prohibited claim pattern detected: '{matches[0]}'")

        # 2. Check for required disclaimer presence
        has_disclaimer = any(kw in lower_text for kw in cls.REQUIRED_DISCLAIMER_KEYWORDS)
        if not has_disclaimer:
            violations.append("Missing required synthetic evaluation disclaimer in report text.")

        is_valid = (len(violations) == 0)
        return is_valid, violations
