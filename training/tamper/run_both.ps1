# Train both tamper encoders on the same data, one after the other (one GPU job at a time). Run from the repo root:
#   powershell -File training\tamper\run_both.ps1
# Each run writes its checkpoint and metrics under var\models\runs\<name>\ and its console log next to them.
# Native resolution: train on 384x384 crops of the full-size screenshot, score whole screenshots at full size. The first
# attempt (whole screenshot shrunk to 704x384) stayed at chance on validation: shrinking washes out the edit traces.
$ErrorActionPreference = "Continue"  # progress bars on stderr must not stop the run
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
$py = Join-Path $root ".venv\Scripts\python.exe"
$env:PYTHONPATH = Join-Path $root "src"
$env:PYTHONUNBUFFERED = "1"  # print each epoch as it finishes
Set-Location (Join-Path $root "training\tamper")
foreach ($run in @(@{name = "resnet18"; args = @("--encoder", "resnet18", "--pretrained", "--lr", "1e-3")}, @{name = "small"; args = @("--encoder", "small")})) {
    $out = Join-Path $root "var\models\runs\$($run.name)"
    New-Item -ItemType Directory -Force $out | Out-Null
    & $py train.py --data (Join-Path $root "data\f1") --out (Join-Path $out "tamper.pt") --native --crop 384 384 --epochs 10 --bs 16 --workers 4 --seed 7 @($run.args) 2>&1 |
        Tee-Object -FilePath (Join-Path $out "console.log")
}
