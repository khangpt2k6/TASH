# TASH - Start both backend and frontend
Write-Host "Starting TASH..." -ForegroundColor Cyan

$backendJob = Start-Job -ScriptBlock {
    Set-Location "c:\Users\2006t\OneDrive\Desktop\TASH\backend"
    python main.py
}

Start-Sleep -Seconds 2

$frontendJob = Start-Job -ScriptBlock {
    Set-Location "c:\Users\2006t\OneDrive\Desktop\TASH\frontend"
    npm run dev
}

Write-Host ""
Write-Host "TASH is running:" -ForegroundColor Green
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor Yellow
Write-Host "  Backend:  http://localhost:8000" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop." -ForegroundColor Gray

try {
    Wait-Job $backendJob, $frontendJob
} finally {
    Stop-Job $backendJob, $frontendJob -ErrorAction SilentlyContinue
    Remove-Job $backendJob, $frontendJob -ErrorAction SilentlyContinue
}
