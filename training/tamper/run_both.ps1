# Train both tamper encoders on the same data, one after the other (one GPU job at a time). Run from the repo root:
#   powershell -File training\tamper\run_both.ps1
# Each run writes its checkpoint and metrics under var\models\runs\<encoder>\ and its console log next to them.
$ErrorActionPreference = "Stop"
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
$py = Join-Path $root ".venv\Scripts\python.exe"
$env:PYTHONPATH = Join-Path $root "src"
Set-Location (Join-Path $root "training\tamper")
foreach ($run in @(@{name = "small"; args = @("--encoder", "small")}, @{name = "resnet18"; args = @("--encoder", "resnet18", "--pretrained")})) {
    $out = Join-Path $root "var\models\runs\$($run.name)"
    New-Item -ItemType Directory -Force $out | Out-Null
    & $py train.py --data (Join-Path $root "data\f1") --out (Join-Path $out "tamper.pt") --epochs 12 --bs 16 --workers 4 --seed 7 @($run.args) 2>&1 |
        Tee-Object -FilePath (Join-Path $out "console.log")
}
