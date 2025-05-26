import asyncio
import logging
import hashlib
from collections import OrderedDict
from typing import Optional

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dungeon_helper")

# Message deduplication cache (limit to N entries)
MAX_CACHE_SIZE = 5000
recent_embed_hashes = OrderedDict()

def get_embed_signature(message) -> Optional[str]:
    """Hash all embeds of a message into one signature string."""
    if not message.embeds:
        return None
    try:
        # Hash all embeds (order matters)
        combined = ''.join(
            str(sorted(embed.to_dict().items())) for embed in message.embeds
        )
        return hashlib.md5(combined.encode()).hexdigest()
    except Exception as e:
        logger.warning(f"[utils_hash] Failed to hash embed: {e}")
        return None

def should_process_message(message) -> bool:
    """Check if this message's embed has changed since last time."""
    sig = get_embed_signature(message)
    if not sig:
        return False  # no embed or invalid

    prev = recent_embed_hashes.get(message.id)
    if prev == sig:
        logger.info(f"[utils_hash] Skipping unchanged embed for message ID: {message.id}")
        return False  # Same content

    # Store and prune cache if needed
    recent_embed_hashes[message.id] = sig
    if len(recent_embed_hashes) > MAX_CACHE_SIZE:
        # Pop the oldest entry
        recent_embed_hashes.popitem(last=False)
    return True

async def safe_send(channel, content=None, delay: float = 0.5, **kwargs):
    """Send a message safely, with throttling and error handling."""
    try:
        await asyncio.sleep(delay)
        return await channel.send(content=content, **kwargs)
    except Exception as e:
        logger.error(f"[utils_hash] Failed to send message: {e}")
        return None

def log_unmatched_embed(embed):
    logger.warning(f"[utils_hash] Embed did not match known patterns: {embed}")