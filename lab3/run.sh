#!/bin/bash

# Memory Scramble - Run Menu

echo "======================================"
echo "  Memory Scramble - Run Menu"
echo "======================================"
echo ""
echo "1) Start server with Docker Compose"
echo "2) Run tests"
echo "3) Run simulation"
echo "4) Stop server"
echo "5) Exit"
echo ""
read -p "Enter your choice (1-5): " choice

case $choice in
    1)
        echo ""
        echo "Starting server with Docker Compose..."
        echo "Server will be available at http://localhost:8080"
        echo "Press Ctrl+C to stop"
        echo ""
        docker-compose up --build
        ;;
    2)
        echo ""
        echo "Running tests in Docker..."
        echo ""
        docker-compose run --rm memory-scramble pytest tests/test_board.py -v
        ;;
    3)
        echo ""
        echo "Running simulation in Docker..."
        echo ""
        docker-compose run --rm memory-scramble python src/simulation.py
        ;;
    4)
        echo ""
        echo "Stopping server..."
        docker-compose down
        echo "Server stopped!"
        ;;
    5)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo "Invalid choice!"
        exit 1
        ;;
esac
