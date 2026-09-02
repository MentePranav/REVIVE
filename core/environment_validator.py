"""
Runtime Environment and Dependency Validator for REVIVE.
Ensures local execution compatibility without requiring any external cloud or payment credentials.
"""

from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple, Union


class EnvironmentValidator:
    """Verifies runtime prerequisites, filesystem layout, and zero-dependency simulation mode."""

    REQUIRED_PACKAGES = ["pydantic", "fastapi", "uvicorn", "pytest"]
    REQUIRED_DIRECTORIES = ["agent", "policy", "execution", "evaluation", "server", "simulator", "tests"]

    @classmethod
    def validate(cls, root_dir: Optional[Union[Path, str]] = None) -> Tuple[bool, List[str], Dict[str, Any]]:
        root = Path(root_dir) if root_dir else Path.cwd()
        errors: List[str] = []
        details: Dict[str, Any] = {
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "packages": {},
            "directories": {},
            "cloud_credentials_required": False,
        }

        # 1. Check Python Version (Requires >= 3.10)
        if sys.version_info < (3, 10):
            errors.append(f"Python 3.10+ is required, but found Python {details['python_version']}.")

        # 2. Check Required Packages
        for pkg in cls.REQUIRED_PACKAGES:
            try:
                __import__(pkg)
                details["packages"][pkg] = "installed"
            except ImportError:
                errors.append(f"Required package '{pkg}' is not installed in the current environment.")
                details["packages"][pkg] = "missing"

        # 3. Check Required Directory Structure
        for dir_name in cls.REQUIRED_DIRECTORIES:
            d_path = root / dir_name
            if d_path.exists() and d_path.is_dir():
                details["directories"][dir_name] = "present"
            else:
                errors.append(f"Required project directory '{dir_name}' not found in {root}.")
                details["directories"][dir_name] = "missing"

        is_valid = (len(errors) == 0)
        return is_valid, errors, details
