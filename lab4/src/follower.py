"""
Key-Value Store with Single-Leader Replication - Follower Server

The follower receives replication requests from the leader and stores data locally.
Handles all requests concurrently.
"""

import os
import logging
from threading import Lock
from flask import Flask, request, jsonify
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('follower')

# Configuration from environment variables
PORT = int(os.environ.get('PORT', 5001))
FOLLOWER_ID = os.environ.get('FOLLOWER_ID', 'follower-1')

logger.info(f"Follower configuration: ID={FOLLOWER_ID}, PORT={PORT}")

# In-memory key-value store
kv_store = {}
kv_lock = Lock()

# Flask app
app = Flask(__name__)
CORS(app)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy", 
        "role": "follower",
        "id": FOLLOWER_ID
    }), 200


@app.route('/replicate', methods=['POST'])
def replicate():
    """
    Receive replication request from leader.
    Updates local store with the replicated data.
    """
    data = request.json
    key = data.get('key')
    value = data.get('value')
    version = data.get('version')
    
    if key is None or value is None or version is None:
        return jsonify({"error": "Missing key, value, or version"}), 400
    
    with kv_lock:
        # Only apply if version is newer or key doesn't exist
        current = kv_store.get(key)
        if current is None or current.get('version', 0) < version:
            kv_store[key] = {"value": value, "version": version}
            logger.info(f"Replicated: {key}={value} (version {version})")
            return jsonify({
                "status": "replicated",
                "key": key,
                "version": version,
                "follower_id": FOLLOWER_ID
            }), 200
        else:
            logger.info(f"Skipped stale replication: {key} (current version {current.get('version')}, received {version})")
            return jsonify({
                "status": "skipped",
                "reason": "stale_version",
                "key": key,
                "current_version": current.get('version'),
                "received_version": version,
                "follower_id": FOLLOWER_ID
            }), 200


@app.route('/get/<key>', methods=['GET'])
def get_value(key):
    """Get a value by key (read from follower)."""
    with kv_lock:
        if key in kv_store:
            return jsonify({
                "key": key, 
                "value": kv_store[key]["value"],
                "version": kv_store[key]["version"],
                "follower_id": FOLLOWER_ID
            }), 200
        else:
            return jsonify({
                "error": "Key not found",
                "follower_id": FOLLOWER_ID
            }), 404


@app.route('/all', methods=['GET'])
def get_all():
    """Get all key-value pairs (for debugging/testing)."""
    with kv_lock:
        return jsonify({
            "role": "follower",
            "id": FOLLOWER_ID,
            "data": {k: v for k, v in kv_store.items()}
        }), 200


@app.route('/config', methods=['GET'])
def get_config():
    """Get current configuration."""
    return jsonify({
        "role": "follower",
        "id": FOLLOWER_ID,
        "port": PORT
    }), 200


if __name__ == '__main__':
    logger.info(f"Starting follower server {FOLLOWER_ID} on port {PORT}")
    # Use threaded=True for concurrent request handling
    app.run(host='0.0.0.0', port=PORT, threaded=True)
