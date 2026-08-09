"""Secret-detection patterns and text-redaction functions."""

import math
import re
from collections import Counter

PATTERNS = [
    ("AWS Access Key ID", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("AWS Secret Access Key", re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?")),
    ("Google API Key", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")),
    ("GitHub Token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("Slack Token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,48}\b")),
    ("Stripe Key", re.compile(r"\b(?:sk|pk)_(?:live|test)_[0-9a-zA-Z]{16,}\b")),
    ("Anthropic API Key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{10,}\b")),
    ("OpenRouter API Key", re.compile(r"\bsk-or-v1-[A-Za-z0-9]{10,}\b")),
    ("Groq API Key", re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b")),
    ("Hugging Face Token", re.compile(r"\bhf_[A-Za-z0-9]{20,}\b")),
    ("Replicate API Token", re.compile(r"\br8_[A-Za-z0-9]{20,}\b")),
    ("Perplexity API Key", re.compile(r"\bpplx-[A-Za-z0-9]{20,}\b")),
    ("xAI API Key", re.compile(r"\bxai-[A-Za-z0-9_-]{20,}\b")),
    ("OpenAI API Key", re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}\b")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")),
    ("JWT Fragment (header/payload)", re.compile(r"\beyJ[A-Za-z0-9_-]{16,}\b")),
    ("Private Key Block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----")),
    ("Bearer Token", re.compile(r"(?i)\bBearer\s+([A-Za-z0-9\-_.=]{10,})")),
    ("Basic Auth URL Credentials", re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://)([^:/\s@]+:[^@/\s]+)@")),
    ("Generic Secret Assignment", re.compile(r"(?i)(?:api[_-]?key|secret(?:[_-]?key)?|token|passwd|password|pwd|access[_-]?key|key)\s*[:=]\s*['\"]?([A-Za-z0-9/+\-_.=]{8,})['\"]?")),
]

_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_HEX_ONLY_RE = re.compile(r"^[0-9a-fA-F]+$")


def mask(value: str) -> str:
    """Preserve two characters at either end of long secrets as a hint."""
    return "*" * len(value) if len(value) <= 8 else value[:2] + "*" * (len(value) - 4) + value[-2:]


def redact_text(text: str) -> tuple[str, list[str]]:
    """Mask known secret formats and return the redacted text and finding labels."""
    findings: list[str] = []

    def make_replacer(label: str):
        def replacer(match: re.Match[str]) -> str:
            findings.append(label)
            if label == "Private Key Block":
                return f"[REDACTED:{label}]"
            secret = next((group for group in reversed(match.groups()) if group), match.group(0))
            return match.group(0).replace(secret, f"[REDACTED:{label}:{mask(secret)}]")
        return replacer

    for label, pattern in PATTERNS:
        text = pattern.sub(make_replacer(label), text)
    return text, findings


def shannon_entropy(value: str) -> float:
    """Return a string's Shannon entropy in bits per character."""
    if not value:
        return 0.0
    counts = Counter(value)
    length = len(value)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def redact_high_entropy(text: str, min_len: int = 20, threshold: float = 4.3) -> tuple[str, list[str]]:
    """Mask probable opaque secrets; this heuristic can yield false positives."""
    findings: list[str] = []
    candidate_re = re.compile(r"[A-Za-z0-9+/_=-]{%d,}" % min_len)

    def replacer(match: re.Match[str]) -> str:
        token = match.group(0)
        if _UUID_RE.match(token):
            return token
        required_entropy = 3.0 if _HEX_ONLY_RE.match(token) else threshold
        if shannon_entropy(token) >= required_entropy:
            findings.append("High-Entropy String")
            return f"[REDACTED:High-Entropy String:{mask(token)}]"
        return token

    return candidate_re.sub(replacer, text), findings
