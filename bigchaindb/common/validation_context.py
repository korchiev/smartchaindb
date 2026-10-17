"""Explicit validation time; authoritative callers use the block header."""
from datetime import datetime, timezone


def timestamp_seconds(value):
    if not isinstance(value, str):
        raise ValueError("Validation time must be an ISO 8601 timestamp")
    # Keep Python 3.6 compatibility, including offsets and fractional seconds.
    text = value.replace("Z", "+0000")
    if len(text) >= 6 and text[-6] in "+-" and text[-3] == ":":
        text = text[:-3] + text[-2:]
    fmt = "%Y-%m-%dT%H:%M:%S.%f%z" if "." in text else "%Y-%m-%dT%H:%M:%S%z"
    return datetime.strptime(text, fmt).timestamp()


def block_validation_time(header_time):
    if isinstance(header_time, str):
        timestamp_seconds(header_time)
        return header_time
    seconds, nanos = header_time.seconds, header_time.nanos
    if not isinstance(seconds, int) or not isinstance(nanos, int) or not 0 <= nanos < 1000000000:
        raise ValueError("Invalid block timestamp")
    # Sidecar Date uses millisecond resolution. Use the same truncation here.
    return datetime.fromtimestamp(seconds + (nanos // 1000000) / 1000.0, timezone.utc).isoformat()
