import re


def safe_error_message(message: str | None) -> str | None:
    """Redact common credentials and bound error messages retained in history."""
    if not message:
        return None

    if "wasm backtrace:" in message:
        context, _, cause = message.partition("\nCaused by:")
        message = cause.strip() or context.split("wasm backtrace:", 1)[0].strip()

    redactions = [
        (
            r"""(?i)(["']?(?:api[-_ ]?key|token|authorization|password|"""
            r"""secret|preimage)["']?)"""
            r"\s*[:=]\s*(?:(?:bearer|basic)\s+)?"
            r"""("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;]+)""",
            r"\1=[redacted]",
        ),
        (r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [redacted]"),
        (r"\b[a-fA-F0-9]{64}\b", "[redacted-hex]"),
    ]
    for pattern, replacement in redactions:
        message = re.sub(pattern, replacement, message)
    # Redact first so truncation cannot expose part of a secret at the boundary.
    return message[:500]
