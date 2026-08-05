$frontend = Start-Process powershell -ArgumentList "-NoExit -Command `"cd frontend; npm run dev`"" -PassThru
$backend = Start-Process powershell -ArgumentList "-NoExit -Command `"cd backend; .venv\Scripts\activate; uvicorn main:app --reload`"" -PassThru

Write-Host "Started frontend (PID: $($frontend.Id)) and backend (PID: $($backend.Id))"
