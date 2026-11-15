"""Test the actual ZIP outside the project, without PATH/PYTHONPATH assistance."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app_info import EXECUTABLE_NAME, PORTABLE_ZIP


def main():
    archive = ROOT / "dist" / PORTABLE_ZIP
    sums = (ROOT / "dist" / "SHA256SUMS.txt").read_text(encoding="ascii").split()[0]
    if hashlib.sha256(archive.read_bytes()).hexdigest() != sums:
        raise RuntimeError("ZIP checksum mismatch")
    location = ROOT / "build" / "独立运行 测试" / "解压后的文件"
    location.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(location)
    executable = location / EXECUTABLE_NAME
    data = executable.read_bytes()
    pe = struct.unpack_from("<I", data, 0x3c)[0]
    subsystem = struct.unpack_from("<H", data, pe + 24 + 68)[0]
    if subsystem != 2:
        raise RuntimeError("The executable is not a windowed Windows application")
    report_path = location / "portable-self-test.json"
    if report_path.exists():
        report_path.unlink()
    environment = os.environ.copy()
    system_root = os.environ.get("SystemRoot") or os.environ["WINDIR"]
    environment["PATH"] = str(Path(system_root) / "System32")
    environment["PYTHONHOME"] = str(location / "没有安装Python")
    environment["PYTHONPATH"] = str(location / "没有项目源码")
    environment.pop("VIRTUAL_ENV", None)
    result = subprocess.run([str(executable), "--self-test", "--report", str(report_path)],
                            cwd=location, env=environment, timeout=90)
    if result.returncode:
        raise RuntimeError(f"Bundled self-check exited {result.returncode}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("status") != "passed" or report.get("frozen") is not True:
        raise RuntimeError(f"Bundled self-check failed: {report}")
    # Check the Chinese double-click entry in the same path, with no Python on
    # PATH. The batch file should find and open the bundled executable directly.
    launcher = location / "开始观看.cmd"
    shutil.copy2(ROOT / "开始观看.cmd", launcher)
    launcher_report = location / "double-click-self-test.json"
    if launcher_report.exists():
        launcher_report.unlink()
    processor = os.environ.get("COMSPEC", str(Path(system_root) / "System32" / "cmd.exe"))
    command = f'{subprocess.list2cmdline([processor])} /d /s /c ""{launcher}" --self-test --report "{launcher_report}""'
    subprocess.run(command, cwd=location, env=environment, check=True, timeout=30,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    deadline = time.monotonic() + 30
    while True:
        try:
            launched = json.loads(launcher_report.read_text(encoding="utf-8"))
            break
        except (OSError, json.JSONDecodeError):
            if time.monotonic() >= deadline:
                raise RuntimeError("The double-click entry did not finish its self-check")
            time.sleep(.1)
    if launched.get("status") != "passed" or launched.get("frozen") is not True:
        raise RuntimeError(f"The double-click entry failed: {launched}")
    report.update(guiSubsystem=True, isolatedWorkingDirectory=True, pythonEnvironmentIgnored=True,
                  doubleClickEntry=True, zipSha256=sums, zipBytes=archive.stat().st_size)
    target = ROOT / "dist" / "portable-verification.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
