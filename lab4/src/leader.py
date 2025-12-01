"""
Key-Value Store with Single-Leader Replication - Leader Server

The leader accepts writes, replicates them to followers using semi-synchronous replication.
Uses configurable write quorum and simulates network lag.
"""

import os
import asyncio
import random
import time
import logging
from threading import Lock
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify
from flask_cors import CORS
import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('leader')

# Configuration from environment variables
PORT = int(os.environ.get('PORT', 5000))
WRITE_QUORUM = int(os.environ.get('WRITE_QUORUM', 2))
MIN_DELAY = int(os.environ.get('MIN_DELAY', 0))  # milliseconds
MAX_DELAY = int(os.environ.get('MAX_DELAY', 1000))  # milliseconds
FOLLOWER_HOSTS = os.environ.get('FOLLOWER_HOSTS', '').split(',')  # comma-separated list
FOLLOWER_HOSTS = [h.strip() for h in FOLLOWER_HOSTS if h.strip()]

logger.info(f"Leader configuration: PORT={PORT}, WRITE_QUORUM={WRITE_QUORUM}, MIN_DELAY={MIN_DELAY}ms, MAX_DELAY={MAX_DELAY}ms")
logger.info(f"Followers: {FOLLOWER_HOSTS}")

# In-memory key-value store
kv_store = {}
kv_lock = Lock()

# Flask app
app = Flask(__name__)
CORS(app)

# Thread pool for concurrent operations
executor = ThreadPoolExecutor(max_workers=20)


async def replicate_to_follower(session: aiohttp.ClientSession, follower_url: str, key: str, value: str, version: int) -> bool:
    """
    Replicate a write to a single follower with simulated network delay.
    Returns True if replication was successful.
    """
    # Simulate network delay
    delay_ms = random.randint(MIN_DELAY, MAX_DELAY)
    await asyncio.sleep(delay_ms / 1000.0)
    
    try:
        async with session.post(
            f"{follower_url}/replicate",
            json={"key": key, "value": value, "version": version},
            timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            if response.status == 200:
                logger.info(f"Replication to {follower_url} successful (delay: {delay_ms}ms)")
                return True
            else:
                logger.warning(f"Replication to {follower_url} failed with status {response.status}")
                return False
    except Exception as e:
        logger.error(f"Replication to {follower_url} failed: {e}")
        return False


async def replicate_to_followers(key: str, value: str, version: int) -> tuple[int, float]:
    """
    Replicate a write to all followers concurrently.
    Uses semi-synchronous replication: waits for WRITE_QUORUM confirmations.
    Returns (number of successful replications, time taken).
    """
    if not FOLLOWER_HOSTS:
        return 0, 0.0
    
    start_time = time.time()
    successful_count = 0
    
    async with aiohttp.ClientSession() as session:
        # Create tasks for all followers
        tasks = [
            replicate_to_follower(session, f"http://{host}", key, value, version)
            for host in FOLLOWER_HOSTS
        ]
        
        # Wait for quorum or all tasks to complete
        pending = set(asyncio.ensure_future(task) for task in tasks)
        
        while pending and successful_count < WRITE_QUORUM:
            done, pending = await asyncio.wait(
                pending, 
                return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                if task.result():
                    successful_count += 1
        
        # Cancel remaining tasks if quorum reached (optional: could let them complete)
        # For semi-sync, we continue replication in background
        # But we return once quorum is met
        
        # Wait for remaining tasks to complete (fire and forget style)
        if pending:
            asyncio.create_task(wait_for_remaining(pending))
    
    elapsed = time.time() - start_time
    return successful_count, elapsed


async def wait_for_remaining(pending):
    """Wait for remaining replication tasks to complete."""
    try:
        for task in pending:
            await task
    except Exception as e:
        logger.error(f"Error in background replication: {e}")


def run_replication(key: str, value: str, version: int) -> tuple[int, float]:
    """Run async replication in the executor."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(replicate_to_followers(key, value, version))
    finally:
        loop.close()


# Version tracking for each key
versions = {}
version_lock = Lock()


def get_next_version(key: str) -> int:
    """Get the next version number for a key."""
    with version_lock:
        versions[key] = versions.get(key, 0) + 1
        return versions[key]


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "role": "leader"}), 200


@app.route('/get/<key>', methods=['GET'])
def get_value(key):
    """Get a value by key."""
    with kv_lock:
        if key in kv_store:
            return jsonify({
                "key": key, 
                "value": kv_store[key]["value"],
                "version": kv_store[key]["version"]
            }), 200
        else:
            return jsonify({"error": "Key not found"}), 404


@app.route('/set', methods=['POST'])
def set_value():
    """
    Set a key-value pair.
    Uses semi-synchronous replication: waits for WRITE_QUORUM followers to confirm.
    """
    data = request.json
    key = data.get('key')
    value = data.get('value')
    
    if key is None or value is None:
        return jsonify({"error": "Missing key or value"}), 400
    
    start_time = time.time()
    
    # Get next version and store locally
    version = get_next_version(key)
    with kv_lock:
        kv_store[key] = {"value": value, "version": version}
    
    # Replicate to followers
    if FOLLOWER_HOSTS:
        success_count, repl_time = run_replication(key, value, version)
        
        if success_count < WRITE_QUORUM:
            # Rollback could be done here, but for simplicity we log a warning
            logger.warning(f"Write quorum not met: {success_count}/{WRITE_QUORUM}")
            return jsonify({
                "error": f"Write quorum not met: {success_count}/{WRITE_QUORUM}",
                "key": key,
                "value": value,
                "version": version
            }), 503
    else:
        success_count = 0
        repl_time = 0
    
    total_time = time.time() - start_time
    
    return jsonify({
        "status": "success",
        "key": key,
        "value": value,
        "version": version,
        "replicated_to": success_count,
        "replication_time_ms": repl_time * 1000,
        "total_time_ms": total_time * 1000
    }), 200


@app.route('/delete/<key>', methods=['DELETE'])
def delete_value(key):
    """Delete a key-value pair."""
    with kv_lock:
        if key in kv_store:
            del kv_store[key]
            # Could replicate delete, but simplified for this lab
            return jsonify({"status": "deleted", "key": key}), 200
        else:
            return jsonify({"error": "Key not found"}), 404


@app.route('/all', methods=['GET'])
def get_all():
    """Get all key-value pairs (for debugging/testing)."""
    with kv_lock:
        return jsonify({
            "role": "leader",
            "data": {k: v for k, v in kv_store.items()}
        }), 200


@app.route('/config', methods=['GET'])
def get_config():
    """Get current configuration."""
    return jsonify({
        "role": "leader",
        "port": PORT,
        "write_quorum": WRITE_QUORUM,
        "min_delay_ms": MIN_DELAY,
        "max_delay_ms": MAX_DELAY,
        "followers": FOLLOWER_HOSTS
    }), 200


if __name__ == '__main__':
    logger.info(f"Starting leader server on port {PORT}")
    # Use threaded=True for concurrent request handling
    app.run(host='0.0.0.0', port=PORT, threaded=True)
