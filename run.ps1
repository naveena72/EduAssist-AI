# One-command start: sets up everything that is missing, then runs the server.
#   .\run.ps1
Set-Location $PSScriptRoot

if (-not (Test-Path venv)) {
    Write-Host "Creating virtual environment..."
    python -m venv venv
    .\venv\Scripts\python.exe -m pip install -r requirements.txt
}
if (-not (Test-Path ml\model\risk_model.joblib)) {
    Write-Host "Training the risk model..."
    .\venv\Scripts\python.exe -m ml.generate_data
    .\venv\Scripts\python.exe -m ml.train
}
if (-not (Test-Path database\eduassist.db)) {
    Write-Host "Creating the sample database..."
    .\venv\Scripts\python.exe -m database.seed
}

Write-Host "`nEduAssist AI running at http://127.0.0.1:8000  (API docs: /docs)  - Ctrl+C to stop`n"
.\venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000
