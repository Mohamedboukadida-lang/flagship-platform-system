"""UUIDv7 ids: sortable by creation time, generated in the application (spec section 5)."""

import os
import time
from uuid import UUID


def new_id() -> UUID:
    """Return a UUIDv7 (RFC 9562): 48-bit Unix milliseconds, then 74 random bits."""
    timestamp_ms = time.time_ns() // 1_000_000
    rand = int.from_bytes(os.urandom(10), "big")
    rand_a = rand >> 68  # 12 bits
    rand_b = rand & ((1 << 62) - 1)
    value = (
        ((timestamp_ms & ((1 << 48) - 1)) << 80)
        | (0x7 << 76)
        | (rand_a << 64)
        | (0b10 << 62)
        | rand_b
    )
    return UUID(int=value)
