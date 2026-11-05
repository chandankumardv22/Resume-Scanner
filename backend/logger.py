# ==============================================================================
# TECH STACK: [Python Logging & Application Security]
# Structured, CloudWatch-Ready Logging with Automated Secret & PII Masking
# ==============================================================================
from __future__ import annotations

import logging
import os
import re
import sys
from typing import Any

# Regular expressions for identifying sensitive credentials and PII
_SECRET_PATTERNS = [
    # API Keys & Tokens
    (re.compile(r"(?i)(api[_-]?key|secret|token|password|salt)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?"), r"\1=***REDACTED***"),
    # Bearer tokens in headers
    (re.compile(r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{16,}"), "Bearer ***REDACTED***"),
    # RapidAPI or Gemini Keys
    (re.compile(r"\b(AIzaSy[a-zA-Z0-9_\-]{33})\b"), "***REDACTED_GEMINI_KEY***"),
    (re.compile(r"\b([a-f0-9]{50})\b"), "***REDACTED_API_KEY***"),
    # Credit cards / Aadhaar-like 12-16 digit numbers
    (re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b"), "***REDACTED_CARD_OR_ID***"),
]


class SensitiveDataFilter(logging.Filter):
    """
    Log filter that intercepts log records and scrubs API keys, passwords,
    session tokens, and sensitive PII from log output before emission.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                msg = record.msg
                for pattern, replacement in _SECRET_PATTERNS:
                    msg = pattern.sub(replacement, msg)
                record.msg = msg

            if record.args:
                if isinstance(record.args, dict):
                    scrubbed = {}
                    for k, v in record.args.items():
                        if any(s in k.lower() for s in ("password", "token", "secret", "salt", "key")):
                            scrubbed[k] = "***REDACTED***"
                        else:
                            scrubbed[k] = v
                    record.args = scrubbed
                elif isinstance(record.args, tuple):
                    record.args = tuple(
                        "***REDACTED***" if isinstance(a, str) and any(s in a.lower() for s in ("password", "salt", "bearer")) else a
                        for a in record.args
                    )
        except Exception:
            pass
        return True


def setup_logging(name: str = "resume_analyzer") -> logging.Logger:
    """
    Configures and returns a structured logger with CloudWatch-compliant output.
    """
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level_name, logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers if already configured
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)

        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        handler.addFilter(SensitiveDataFilter())

        logger.addHandler(handler)
        logger.propagate = False

    return logger


logger = setup_logging()
