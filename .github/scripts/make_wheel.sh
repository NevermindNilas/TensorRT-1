#!/usr/bin/env bash
# Assemble a bindings-only TensorRT wheel (Linux).
#   $1 = path to compiled tensorrt.so
#   $2 = wheel tag, e.g. cp314-cp314-linux_x86_64
#   $3 = python interpreter (default python3)
set -euo pipefail

MODULE="$1"
TAG="$2"
PY="${3:-python3}"
TRT_VER="${TRT_VER:-10.16.0.72}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

WHL="$(mktemp -d)/whl"
mkdir -p "${WHL}/tensorrt" "${WHL}/tensorrt-${TRT_VER}.dist-info"

# Processed package __init__ (fills ##TOKENS##)
"${PY}" "${REPO_ROOT}/python/scripts/process_wheel_template.py" \
  --src-dir "${REPO_ROOT}/python/packaging/bindings_wheel" \
  --dst-dir "${WHL}" \
  --filepath tensorrt/__init__.py \
  --trt-module tensorrt --trt-py-version "${TRT_VER}" \
  --cuda-version 13.2 --trt-version 10.16.0 \
  --trt-nvinfer-name nvinfer --trt-onnxparser-name nvonnxparser --plugin-disabled 0
! grep -q '##' "${WHL}/tensorrt/__init__.py"

cp "${MODULE}" "${WHL}/tensorrt/$(basename "${MODULE}")"

{
  printf 'Metadata-Version: 2.1\n'
  printf 'Name: tensorrt\n'
  printf 'Version: %s\n' "${TRT_VER}"
  printf 'Summary: Unofficial cp3%s build of TensorRT 10.16 bindings (bindings-only)\n' "${PY_MINOR:-}"
  printf 'Home-page: https://github.com/NevermindNilas/tensorrt-py3.14\n'
  printf 'License: Apache-2.0 bindings; NVIDIA EULA for separately-provided libs\n'
  printf 'Requires-Python: >=3.%s,<3.%s\n' "${PY_MINOR}" "$((PY_MINOR + 1))"
  # Runtime libs (closed) pulled from NVIDIA's index: --extra-index-url https://pypi.nvidia.com
  printf 'Requires-Dist: tensorrt-cu13-libs==%s\n' "${TRT_VER}"
} > "${WHL}/tensorrt-${TRT_VER}.dist-info/METADATA"
{
  printf 'Wheel-Version: 1.0\n'
  printf 'Generator: tas-cp314-poc\n'
  printf 'Root-Is-Purelib: false\n'
  printf 'Tag: %s\n' "${TAG}"
} > "${WHL}/tensorrt-${TRT_VER}.dist-info/WHEEL"

mkdir -p dist
"${PY}" -m wheel pack "${WHL}" -d dist
ls -la dist/
"${PY}" -m zipfile -l dist/*.whl
