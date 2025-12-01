#!/bin/bash

# Run script for Lab 4: Key-Value Store with Single-Leader Replication

set -e

echo "=========================================="
echo "Lab 4: Key-Value Store with Replication"
echo "=========================================="

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "Error: docker-compose is not installed"
    exit 1
fi

# Parse command line arguments
case "${1:-start}" in
    start)
        echo "Starting services..."
        docker-compose up -d
        echo ""
        echo "Services started! Endpoints:"
        echo "  Leader:    http://localhost:8000"
        echo "  Follower1: http://localhost:8001"
        echo "  Follower2: http://localhost:8002"
        echo "  Follower3: http://localhost:8003"
        echo "  Follower4: http://localhost:8004"
        echo "  Follower5: http://localhost:8005"
        echo ""
        echo "Example usage:"
        echo "  curl http://localhost:8000/health"
        echo "  curl -X POST http://localhost:8000/set -H 'Content-Type: application/json' -d '{\"key\": \"test\", \"value\": \"hello\"}'"
        echo "  curl http://localhost:8000/get/test"
        ;;
    
    stop)
        echo "Stopping services..."
        docker-compose down
        echo "Services stopped."
        ;;
    
    restart)
        echo "Restarting services..."
        docker-compose down
        docker-compose up -d
        echo "Services restarted."
        ;;
    
    logs)
        docker-compose logs -f "${2:-}"
        ;;
    
    test)
        echo "Running integration tests..."
        echo "Make sure services are running (./run.sh start)"
        pip install -r requirements.txt -q
        pytest tests/test_integration.py -v
        ;;
    
    perf)
        echo "Running performance analysis..."
        pip install -r requirements.txt -q
        python performance_analysis.py
        ;;
    
    status)
        echo "Checking service status..."
        docker-compose ps
        echo ""
        echo "Health checks:"
        for port in 8000 8001 8002 8003 8004 8005; do
            if curl -s "http://localhost:$port/health" > /dev/null 2>&1; then
                echo "  Port $port: ✓ healthy"
            else
                echo "  Port $port: ✗ unavailable"
            fi
        done
        ;;
    
    build)
        echo "Building Docker images..."
        docker-compose build
        ;;
    
    *)
        echo "Usage: $0 {start|stop|restart|logs|test|perf|status|build}"
        echo ""
        echo "Commands:"
        echo "  start   - Start all services"
        echo "  stop    - Stop all services"
        echo "  restart - Restart all services"
        echo "  logs    - View logs (optionally specify service: logs leader)"
        echo "  test    - Run integration tests"
        echo "  perf    - Run performance analysis"
        echo "  status  - Check service status"
        echo "  build   - Rebuild Docker images"
        exit 1
        ;;
esac
