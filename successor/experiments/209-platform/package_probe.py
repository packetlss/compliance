#!/usr/bin/env python3
"""Commodity packaging harness; no Python application or legacy dependency."""
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import tarfile
import tempfile
import time

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]


def main():
    with tempfile.TemporaryDirectory(prefix="experiment209-package-") as directory:
        stage = Path(directory).resolve()
        binary = stage / "probe"
        environment = dict(os.environ, CGO_ENABLED="0", GOTOOLCHAIN="local")
        build = stage / "build"
        shutil.copytree(ROOT, build, ignore=shutil.ignore_patterns("__pycache__"))
        subprocess.run(["go", "build", "-mod=readonly", "-trimpath", "-ldflags=-s -w", "-o", str(binary), "./cmd/probe"], cwd=build, env=environment, check=True)
        shutil.rmtree(build)
        with tarfile.open(stage / "package.tar.gz", "w:gz") as archive:
            archive.add(binary, arcname="probe")
        shutil.copytree(ROOT / "fixtures/input", stage / "inputs")
        (stage / "inputs/.admission.lock").touch()
        # Private policy is supplied independently, never embedded in the executable.
        assert (stage / "inputs/source-private.json").is_file()
        if platform.system() == "Linux":
            test = subprocess.run(["unshare", "-Urn", "true"], capture_output=True)
            if test.returncode == 0:
                prefix = ["unshare", "-Urn", (shutil.which("chroot") or "/usr/sbin/chroot"), str(stage)]
            else:
                prefix = ["sudo", "-n", "unshare", "--net", (shutil.which("chroot") or "/usr/sbin/chroot"), f"--userspec={os.getuid()}:{os.getgid()}", str(stage)]
            command_binary, inputs, record = "/probe", "/inputs", "/record.json"
            isolation = "new network namespace + chroot containing only binary and synthetic inputs"
        elif platform.system() == "Darwin":
            profile = f'(version 1) (allow default) (deny network*) (deny file-read* (subpath {json.dumps(str(REPO))}))'
            prefix = ["/usr/bin/sandbox-exec", "-p", profile]
            command_binary, inputs, record = str(binary), str(stage / "inputs"), str(stage / "record.json")
            isolation = "native sandbox-exec denies network and repository reads"
        else:
            raise RuntimeError("unsupported native platform")

        def invoke(*args, success=True):
            start = time.perf_counter()
            proc = subprocess.run(prefix + [command_binary, *args], cwd=stage,
                                  env={"PATH": "/usr/bin:/bin", "HOME": str(stage)},
                                  capture_output=True, text=True, timeout=10)
            elapsed = time.perf_counter() - start
            if proc.returncode != (0 if success else 1):
                raise AssertionError((args, proc.returncode, proc.stderr))
            return proc.stdout, elapsed

        startup = [invoke(success=False)[1] for _ in range(5)]
        assessment = []
        for i in range(5):
            _, elapsed = invoke("assess", inputs, "2026-09-26T12:00:00Z", record + str(i))
            assessment.append(elapsed)
        before, _ = invoke("explain", record + "0")
        summary = json.loads(before)
        assert summary["Subjects"] == 2 and summary["Status"] == "FAIL"
        assert summary["Objectives"]["C/access"] == "FAIL"
        c = next(r for r in summary["Record"]["Results"] if r["Subject"] == "C")
        audit = next(o for o in c["Outcomes"] if o["Check"] == "audit")
        assert audit["Status"] == "WAIVED" and audit["Underlying"] == "FAIL"
        assert audit["Selected"][0]["Facts"]["audit"] is False
        shutil.rmtree(stage / "inputs")
        explanations = []
        for _ in range(5):
            after, elapsed = invoke("explain", record + "0")
            assert json.loads(after) == summary
            explanations.append(elapsed)
        invoke("assess", inputs, "2026-09-28T12:00:00Z", record, success=False)
        assert not (stage / "record.json").exists()
        # A refusal cannot present one of the retained historical results as its output.
        assert json.loads(invoke("explain", record + "0")[0]) == summary
        subprocess.run(["go", "version", "-m", str(binary)], check=True)
        print(json.dumps({"os": platform.system(), "architecture": platform.machine(),
                          "platform": platform.platform(), "isolation": isolation,
                          "binary_bytes": binary.stat().st_size,
                          "gzip_package_bytes": (stage / "package.tar.gz").stat().st_size,
                          "record_bytes": (stage / "record.json0").stat().st_size,
                          "samples": 5,
                          "startup_usage_median_seconds": statistics.median(startup),
                          "assessment_median_seconds": statistics.median(assessment),
                          "explanation_median_seconds": statistics.median(explanations),
                          "measurement": "wall time includes process and isolation wrapper; warm filesystem; not evaluator-only latency"}, indent=2))


if __name__ == "__main__":
    main()
