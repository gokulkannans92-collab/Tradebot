$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Starting TradeBot backend with Docker Compose..."
docker compose up --build --remove-orphans
