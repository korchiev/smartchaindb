#!/bin/bash
# Script to test BUY_OFFER transaction type in Docker container

echo "🚀 Testing BUY_OFFER Transaction Type in Docker"
echo "================================================"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose is not installed. Please install it first."
    exit 1
fi

echo "✅ Docker environment check passed"

# Build the BigchainDB container if not already built
echo "🔨 Building BigchainDB container..."
docker-compose build bigchaindb

if [ $? -ne 0 ]; then
    echo "❌ Failed to build BigchainDB container"
    exit 1
fi

echo "✅ BigchainDB container built successfully"

# Run the BUY_OFFER test in the container
echo "🧪 Running BUY_OFFER tests in Docker container..."
echo ""

docker-compose run --rm bigchaindb python examples/docker_test_buy_offer.py

# Check the exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 BUY_OFFER tests completed successfully!"
    echo "✅ The BUY_OFFER transaction type is working correctly in Docker!"
else
    echo ""
    echo "💥 BUY_OFFER tests failed!"
    echo "❌ There might be issues with the implementation"
fi

echo ""
echo "🏁 Test completed. Container will be cleaned up automatically."
