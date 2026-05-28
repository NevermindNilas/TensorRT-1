# Assemble a bindings-only TensorRT wheel (Windows).
#   -Module : path to the compiled binding (tensorrt.dll or tensorrt.pyd)
#   -Tag    : wheel tag, e.g. cp314-cp314-win_amd64
param(
  [Parameter(Mandatory)][string]$Module,
  [Parameter(Mandatory)][string]$Tag
)
$ErrorActionPreference = "Stop"

$TrtVer = $env:TRT_VER; if (-not $TrtVer) { $TrtVer = "10.16.1.11" }
$repo = $env:GITHUB_WORKSPACE
$whl = Join-Path $env:RUNNER_TEMP "whl"
Remove-Item -Recurse -Force $whl -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path "$whl\tensorrt", "$whl\tensorrt-$TrtVer.dist-info" | Out-Null

python "$repo\python\scripts\process_wheel_template.py" `
  --src-dir "$repo\python\packaging\bindings_wheel" --dst-dir "$whl" `
  --filepath tensorrt/__init__.py `
  --trt-module tensorrt --trt-py-version $TrtVer `
  --cuda-version 13.2 --trt-version 10.16.1 `
  --trt-nvinfer-name nvinfer --trt-onnxparser-name nvonnxparser --plugin-disabled 0
if (Select-String -Path "$whl\tensorrt\__init__.py" -Pattern '##' -Quiet) { throw "unfilled template token" }

# Python loads the extension as tensorrt.tensorrt; on Windows it must be a .pyd
Copy-Item $Module "$whl\tensorrt\tensorrt.pyd" -Force

$next = [int]$env:PY_MINOR + 1
@(
  "Metadata-Version: 2.1",
  "Name: tensorrt",
  "Version: $TrtVer",
  "Summary: Unofficial cp3$env:PY_MINOR build of TensorRT 10.16 bindings (bindings-only)",
  "Home-page: https://github.com/NevermindNilas/tensorrt-py3.14",
  "License: Apache-2.0 bindings; NVIDIA EULA for separately-provided libs",
  "Requires-Python: >=3.$env:PY_MINOR,<3.$next",
  "Requires-Dist: tensorrt-cu13-libs==$TrtVer"
) | Set-Content -Encoding ascii "$whl\tensorrt-$TrtVer.dist-info\METADATA"
@(
  "Wheel-Version: 1.0",
  "Generator: tas-cp314-poc",
  "Root-Is-Purelib: false",
  "Tag: $Tag"
) | Set-Content -Encoding ascii "$whl\tensorrt-$TrtVer.dist-info\WHEEL"

New-Item -ItemType Directory -Force -Path dist | Out-Null
python -m wheel pack "$whl" -d dist
Get-ChildItem dist
python -m zipfile -l (Get-ChildItem dist\*.whl | Select-Object -First 1).FullName
