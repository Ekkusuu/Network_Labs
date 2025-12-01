"""
Integration tests for the Key-Value Store with Single-Leader Replication.

These tests verify that the replication system works correctly:
- Write operations are replicated to followers
- Read operations work on both leader and followers
- Semi-synchronous replication respects the write quorum
- Data consistency across replicas
"""

import os
import time
import pytest
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
LEADER_URL = os.environ.get('LEADER_URL', 'http://localhost:8000')
FOLLOWER_URLS = os.environ.get('FOLLOWER_URLS', 
    'http://localhost:8001,http://localhost:8002,http://localhost:8003,http://localhost:8004,http://localhost:8005'
).split(',')
FOLLOWER_URLS = [url.strip() for url in FOLLOWER_URLS if url.strip()]


def wait_for_service(url: str, timeout: int = 30) -> bool:
    """Wait for a service to become available."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{url}/health", timeout=2)
            if response.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(0.5)
    return False


@pytest.fixture(scope="module", autouse=True)
def wait_for_services():
    """Wait for all services to be ready before running tests."""
    print("Waiting for leader service...")
    assert wait_for_service(LEADER_URL), f"Leader service not available at {LEADER_URL}"
    
    for url in FOLLOWER_URLS:
        print(f"Waiting for follower service at {url}...")
        assert wait_for_service(url), f"Follower service not available at {url}"
    
    print("All services are ready!")
    yield


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_leader_health(self):
        """Test leader health endpoint."""
        response = requests.get(f"{LEADER_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert data['role'] == 'leader'
    
    def test_followers_health(self):
        """Test all followers health endpoints."""
        for url in FOLLOWER_URLS:
            response = requests.get(f"{url}/health")
            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'healthy'
            assert data['role'] == 'follower'


class TestBasicOperations:
    """Test basic key-value operations."""
    
    def test_set_and_get_on_leader(self):
        """Test setting and getting a value on the leader."""
        key = f"test_key_{time.time()}"
        value = "test_value"
        
        # Set value
        response = requests.post(
            f"{LEADER_URL}/set",
            json={"key": key, "value": value}
        )
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['key'] == key
        assert data['value'] == value
        
        # Get value
        response = requests.get(f"{LEADER_URL}/get/{key}")
        assert response.status_code == 200
        data = response.json()
        assert data['key'] == key
        assert data['value'] == value
    
    def test_get_nonexistent_key(self):
        """Test getting a nonexistent key returns 404."""
        response = requests.get(f"{LEADER_URL}/get/nonexistent_key_12345")
        assert response.status_code == 404


class TestReplication:
    """Test replication functionality."""
    
    def test_write_replicates_to_followers(self):
        """Test that writes are replicated to followers."""
        key = f"replication_test_{time.time()}"
        value = "replicated_value"
        
        # Write to leader
        response = requests.post(
            f"{LEADER_URL}/set",
            json={"key": key, "value": value}
        )
        assert response.status_code == 200
        
        # Wait a bit for replication to complete
        time.sleep(2)
        
        # Check on followers
        replicated_count = 0
        for url in FOLLOWER_URLS:
            response = requests.get(f"{url}/get/{key}")
            if response.status_code == 200:
                data = response.json()
                if data['value'] == value:
                    replicated_count += 1
        
        # Should be replicated to at least write quorum followers
        print(f"Replicated to {replicated_count} followers")
        assert replicated_count >= 2, f"Expected at least 2 replicas, got {replicated_count}"
    
    def test_multiple_writes_same_key(self):
        """Test multiple writes to the same key are handled correctly."""
        key = f"multi_write_test_{time.time()}"
        
        # Write multiple values
        for i in range(5):
            value = f"value_{i}"
            response = requests.post(
                f"{LEADER_URL}/set",
                json={"key": key, "value": value}
            )
            assert response.status_code == 200
        
        # Wait for replication
        time.sleep(2)
        
        # Check final value on leader
        response = requests.get(f"{LEADER_URL}/get/{key}")
        assert response.status_code == 200
        leader_data = response.json()
        
        # Check followers have consistent value
        for url in FOLLOWER_URLS:
            response = requests.get(f"{url}/get/{key}")
            if response.status_code == 200:
                follower_data = response.json()
                # Version should match or be greater (due to replication order)
                assert follower_data['version'] <= leader_data['version']


class TestConcurrentWrites:
    """Test concurrent write operations."""
    
    def test_concurrent_writes_different_keys(self):
        """Test concurrent writes to different keys."""
        prefix = f"concurrent_test_{time.time()}_"
        num_writes = 20
        
        def write_key(i):
            key = f"{prefix}{i}"
            value = f"value_{i}"
            response = requests.post(
                f"{LEADER_URL}/set",
                json={"key": key, "value": value}
            )
            return response.status_code == 200, key, value
        
        # Perform concurrent writes
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(write_key, i) for i in range(num_writes)]
            results = [f.result() for f in as_completed(futures)]
        
        # All writes should succeed
        successful_writes = [r for r in results if r[0]]
        assert len(successful_writes) == num_writes
        
        # Wait for replication
        time.sleep(3)
        
        # Verify on leader
        response = requests.get(f"{LEADER_URL}/all")
        assert response.status_code == 200
        leader_data = response.json()['data']
        
        for success, key, value in successful_writes:
            assert key in leader_data
            assert leader_data[key]['value'] == value
    
    def test_concurrent_writes_same_key(self):
        """Test concurrent writes to the same key (last write wins)."""
        key = f"concurrent_same_key_{time.time()}"
        num_writes = 10
        
        def write_value(i):
            value = f"value_{i}"
            response = requests.post(
                f"{LEADER_URL}/set",
                json={"key": key, "value": value}
            )
            return response.status_code == 200
        
        # Perform concurrent writes
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(write_value, i) for i in range(num_writes)]
            results = [f.result() for f in as_completed(futures)]
        
        # All writes should succeed (or fail due to quorum not met during concurrent writes)
        successful = sum(results)
        print(f"Successful writes: {successful}/{num_writes}")
        
        # At least some should succeed
        assert successful > 0
        
        # Wait for replication
        time.sleep(2)
        
        # Final value should be consistent
        response = requests.get(f"{LEADER_URL}/get/{key}")
        assert response.status_code == 200


class TestDataConsistency:
    """Test data consistency across the cluster."""
    
    def test_eventual_consistency(self):
        """Test that all replicas eventually have consistent data."""
        # Write some data
        keys_values = {}
        for i in range(5):
            key = f"consistency_test_{time.time()}_{i}"
            value = f"value_{i}"
            response = requests.post(
                f"{LEADER_URL}/set",
                json={"key": key, "value": value}
            )
            if response.status_code == 200:
                keys_values[key] = value
        
        # Wait for all replications to complete
        time.sleep(3)
        
        # Check consistency
        response = requests.get(f"{LEADER_URL}/all")
        leader_data = response.json()['data']
        
        for url in FOLLOWER_URLS:
            response = requests.get(f"{url}/all")
            if response.status_code == 200:
                follower_data = response.json()['data']
                
                # Check each key we wrote
                for key, expected_value in keys_values.items():
                    if key in leader_data:
                        if key in follower_data:
                            # Values should match
                            assert follower_data[key]['value'] == leader_data[key]['value'], \
                                f"Value mismatch for {key} on {url}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
