# ParkMyCar Localhost Runner
# Starts both the Next.js Frontend/API (port 3000) and Python ANPR Service (port 8000)
$root = Resolve-Path "$PSScriptRoot\.."
Set-Location $root
$env:PYTHONPATH = $root.Path

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  PARKMYCAR - SMART PARKING & ANPR SYSTEM" -ForegroundColor Green
Write-Host "  HackFront India Grand Finale 2026" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Starting Next.js App on http://localhost:3000..." -ForegroundColor Cyan
Write-Host "Starting Python ANPR FastAPI on http://localhost:8000..." -ForegroundColor Cyan
Write-Host ""

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$($root.Path)'; `$env:PYTHONPATH='$($root.Path)'; python -m uvicorn anpr_service.main:app --port 8000 --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$($root.Path)'; node ./node_modules/next/dist/bin/next dev --port 3000"

Write-Host "Both services are running in their dedicated terminals!" -ForegroundColor Green
Write-Host "- Web App & ANPR Dashboard: http://localhost:3000/workspace" -ForegroundColor Yellow
Write-Host "- ANPR Swagger API Docs:    http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host ""
