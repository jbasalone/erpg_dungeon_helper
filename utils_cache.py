# utils_cache.py
import time

# Simple in-memory cache: { (channel_id, message_id): (timestamp, message) }
MESSAGE_CACHE = {}
MESSAGE_CACHE_EXPIRY = 2.0  # seconds

async def get_message_with_cache(channel, message_id):
    key = (channel.id, message_id)
    now = time.time()
    entry = MESSAGE_CACHE.get(key)
    if entry and now - entry[0] < MESSAGE_CACHE_EXPIRY:
        return entry[1]
    msg = await channel.fetch_message(message_id)
    MESSAGE_CACHE[key] = (now, msg)
    return msg