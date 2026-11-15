"""Build the offline, windowed Windows x64 viewer and a beginner-friendly ZIP."""
from __future__ import annotations

import hashlib
from importlib import metadata
from pathlib import Path
import platform
import struct
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app_info import APP_NAME, EXECUTABLE_NAME, PORTABLE_ZIP, VERSION


def license_files():
    """Include the license files shipped with the embedded runtime and libraries."""
    result = {}
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        raise RuntimeError("Python's license file was not found")
    result["licenses/Python.txt"] = python_license
    for package in ("numpy", "pyinstaller"):
        dist = metadata.distribution(package)
        found = False
        for file in dist.files or ():
            relative = Path(str(file))
            if relative.name.upper().startswith(("LICENSE", "COPYING")):
                source = Path(dist.locate_file(file))
                if source.is_file():
                    destination = f"licenses/{package}/{relative.as_posix()}"
                    result[destination] = source
                    found = True
        if not found:
            raise RuntimeError(f"No license file was found for {package}")
    for file in (Path(sys.base_prefix) / "tcl").rglob("license.terms"):
        result[f"licenses/TclTk/{file.parent.name}.txt"] = file
    return result


def main():
    if sys.platform != "win32" or struct.calcsize("P") != 8 or platform.machine().lower() not in ("amd64", "x86_64"):
        raise SystemExit("Build this distribution with 64-bit Python on Windows x64.")
    build = ROOT / "build" / "portable"
    output = ROOT / "dist"
    build.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    version_file = build / "version_info.txt"
    version_numbers = tuple(map(int, VERSION.split("."))) + (0,)
    version_file.write_text(
        "VSVersionInfo(\n"
        f" ffi=FixedFileInfo(filevers={version_numbers!r}, prodvers={version_numbers!r}, mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0,0)),\n"
        " kids=[StringFileInfo([StringTable('080404B0', [\n"
        f" StringStruct('FileDescription', {APP_NAME!r}), StringStruct('ProductName', {APP_NAME!r}),\n"
        f" StringStruct('FileVersion', {VERSION!r}), StringStruct('ProductVersion', {VERSION!r}),\n"
        f" StringStruct('OriginalFilename', {EXECUTABLE_NAME!r}), StringStruct('InternalName', 'EyeBeyond')\n"
        " ])]), VarFileInfo([VarStruct('Translation', [2052,1200])])]\n)\n",
        encoding="utf-8",
    )
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
               "--noupx", "--icon", "NONE", "--name", "EyeBeyond", "--distpath", str(output),
               "--workpath", str(build / "work"), "--specpath", str(build),
               "--version-file", str(version_file), "--paths", str(ROOT), str(ROOT / "desktop.py")]
    subprocess.run(command, cwd=ROOT, check=True)
    executable = output / "EyeBeyond.exe"
    guide = (
        f"{APP_NAME}  {VERSION}\r\n\r\n"
        "1. 先把这个压缩包完整解压到一个文件夹。\r\n"
        f"2. 双击「{EXECUTABLE_NAME}」。\r\n"
        "3. 点击窗口下方的按钮，即可暂停、重播、全屏或退出。\r\n\r\n"
        "动画约 2 分 24 秒，会自动循环。关闭窗口也能退出。\r\n"
        "程序已经自带运行环境，可以离线观看。无需安装 Python 或 PowerShell。\r\n"
        "此版本适用于 Windows 10 / 11 的 x64 电脑。\r\n"
    )
    archive = output / PORTABLE_ZIP
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(executable, EXECUTABLE_NAME)
        bundle.writestr("先看这里.txt", b"\xef\xbb\xbf" + guide.encode("utf-8"))
        for name, path in license_files().items():
            bundle.write(path, name)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / "SHA256SUMS.txt").write_text(f"{checksum}  {archive.name}\n", encoding="ascii")
    print(f"Built {archive.name}: {archive.stat().st_size / 1024 / 1024:.1f} MiB")
    print(f"SHA256: {checksum}")


if __name__ == "__main__":
    main()
