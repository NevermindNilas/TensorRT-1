#!/usr/bin/env python3
"""Detect the latest publicly *buildable* TensorRT version for the cp314 fork.

"Buildable" means all three exist for the same version:
  1. tensorrt-cu13-libs wheel on pypi.nvidia.com   (closed runtime libs)
  2. a public GA tarball at developer.nvidia.com    (headers + import libs)
  3. an upstream NVIDIA/TensorRT OSS ref             (the pybind binding source)

It also reports the *stop signal*: once NVIDIA ships an official cp314
`tensorrt-cu13-bindings` wheel, this fork is obsolete and the automation
should retire (the caller opens an issue and skips building).

Run locally for a human-readable verdict; in GitHub Actions it also writes
step outputs to $GITHUB_OUTPUT.
"""
import json, os, re, sys, urllib.request

FORK = os.environ.get("FORK_REPO", "NevermindNilas/tensorrt-py3.14")
PY_TAG = "cp314"
CUDA_SUFFIXES = ["13.2", "13.3", "13.1", "13.0"]  # GA tarball cuda-XX variants to probe
NV_DL = "https://developer.nvidia.com/downloads/compute/machine-learning/tensorrt"


def _get(url, timeout=30, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "cp314-detect"})
    return urllib.request.urlopen(req, timeout=timeout)


def _text(url, **kw):
    return _get(url, **kw).read().decode("utf-8", "replace")


def _gh(path):
    h = {"User-Agent": "cp314-detect", "Accept": "application/vnd.github+json"}
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return _text(f"https://api.github.com{path}", headers=h)


def nvidia_index_files(pkg):
    try:
        html = _text(f"https://pypi.nvidia.com/{pkg}/")
    except Exception:
        return []
    return re.findall(r">([^<]+\.whl)<", html)


def official_cp314_exists():
    """Stop signal: NVIDIA ships an official cp314 bindings wheel."""
    for pkg in ("tensorrt-cu13-bindings", "tensorrt-bindings", "tensorrt-cu12-bindings"):
        if any(PY_TAG in f for f in nvidia_index_files(pkg)):
            return True
    return False


def libs_versions():
    """All 4-part tensorrt-cu13-libs versions, newest first."""
    vers = set()
    for f in nvidia_index_files("tensorrt-cu13-libs"):
        m = re.search(r"-(\d+\.\d+\.\d+\.\d+)-", f)
        if m:
            vers.add(m.group(1))
    return sorted(vers, key=lambda v: [int(x) for x in v.split(".")], reverse=True)


def url_ok(url):
    try:
        # ranged GET so we transfer ~1 byte; follow redirects to the CDN
        r = _get(url, timeout=25, headers={"User-Agent": "cp314-detect", "Range": "bytes=0-0"})
        return r.status in (200, 206)
    except Exception:
        return False


def ga_tarball(full, seg):
    """Return cuda suffix whose linux GA tarball is downloadable, else None."""
    for cu in CUDA_SUFFIXES:
        url = f"{NV_DL}/{seg}/tars/TensorRT-{full}.Linux.x86_64-gnu.cuda-{cu}.tar.gz"
        if url_ok(url):
            return cu
    return None


def oss_ref_for(full):
    """Resolve an upstream OSS git ref (tag or branch) carrying this version's source."""
    maj, minr, pat, _ = full.split(".")
    try:
        tags = {t["name"] for t in json.loads(_gh("/repos/NVIDIA/TensorRT/tags?per_page=100"))}
    except Exception:
        tags = set()
    for cand in (f"v{maj}.{minr}.{pat}", f"v{maj}.{minr}"):
        if cand in tags:
            return cand
    # patch releases sometimes live on a release branch without a tag
    branch = f"release/{maj}.{minr}"
    try:
        _gh(f"/repos/NVIDIA/TensorRT/branches/{branch}")
        return branch
    except Exception:
        return None


def already_released(full):
    try:
        _gh(f"/repos/{FORK}/releases/tags/v{full}-{PY_TAG}")
        return True
    except Exception:
        return False


def main():
    out = {"should_build": "false", "official": "false", "trt_version": "",
           "trt_url_seg": "", "cuda_suffix": "", "oss_ref": ""}
    log = []

    if official_cp314_exists():
        out["official"] = "true"
        log.append("STOP: NVIDIA ships official cp314 bindings -> fork obsolete, skip build")
        return finish(out, log)

    for full in libs_versions():
        maj, minr, pat, _ = full.split(".")
        seg = f"{maj}.{minr}.{pat}"
        cu = ga_tarball(full, seg)
        ref = oss_ref_for(full)
        log.append(f"candidate {full}: libs=yes ga_tarball={cu or 'no'} oss_ref={ref or 'no'}")
        if cu and ref:
            out["trt_version"] = full
            out["trt_url_seg"] = seg
            out["cuda_suffix"] = cu
            out["oss_ref"] = ref
            if already_released(full):
                log.append(f"latest buildable {full} already released -> up to date, skip")
            else:
                out["should_build"] = "true"
                log.append(f"BUILD: {full} (oss_ref={ref}, cuda-{cu})")
            return finish(out, log)
        log.append(f"  {full} not fully buildable yet, trying older")

    log.append("no buildable version found")
    return finish(out, log)


def finish(out, log):
    print("\n".join(log))
    print("---")
    for k, v in out.items():
        print(f"{k}={v}")
    gho = os.environ.get("GITHUB_OUTPUT")
    if gho:
        with open(gho, "a") as f:
            for k, v in out.items():
                f.write(f"{k}={v}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
