# PowerShell script to test BUY_OFFER transaction type in Docker container

Write-Host "🚀 Testing BUY_OFFER Transaction Type in Docker" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green

# Check if Docker is running
try {
    docker info | Out-Null
    Write-Host "✅ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker is not running. Please start Docker first." -ForegroundColor Red
    exit 1
}

# Check if docker-compose is available
try {
    docker-compose --version | Out-Null
    Write-Host "✅ docker-compose is available" -ForegroundColor Green
} catch {
    Write-Host "❌ docker-compose is not available. Please install it first." -ForegroundColor Red
    exit 1
}

Write-Host "✅ Docker environment check passed" -ForegroundColor Green

# Build the BigchainDB container if not already built
Write-Host "🔨 Building BigchainDB container..." -ForegroundColor Yellow
$buildResult = docker-compose build bigchaindb

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to build BigchainDB container" -ForegroundColor Red
    exit 1
}

Write-Host "✅ BigchainDB container built successfully" -ForegroundColor Green

# Run the BUY_OFFER test in the container
Write-Host "🧪 Running BUY_OFFER tests in Docker container..." -ForegroundColor Yellow
Write-Host ""

$testResult = docker-compose run --rm bigchaindb python examples/docker_test_buy_offer.py

# Check the exit code
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "🎉 BUY_OFFER tests completed successfully!" -ForegroundColor Green
    Write-Host "✅ The BUY_OFFER transaction type is working correctly in Docker!" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "💥 BUY_OFFER tests failed!" -ForegroundColor Red
    Write-Host "❌ There might be issues with the implementation" -ForegroundColor Red
}

Write-Host ""
Write-Host "🏁 Test completed. Container will be cleaned up automatically." -ForegroundColor Cyan
