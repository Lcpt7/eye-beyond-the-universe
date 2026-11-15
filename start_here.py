"""Prepare a private local environment for the optional source-code launcher."""
import os
from pathlib import Path
import subprocess
import sys
import venv

from app_info import RELEASES_URL

ROOT = Path(__file__).resolve().parent
PROBE = (
    "import sys,re,numpy,tkinter; "
    r"v=tuple(map(int,re.match(r'(\d+)\.(\d+)',numpy.__version__).groups())); "
    "sys.exit(not(sys.version_info >= (3,10) and (1,24) <= v < (3,0)))"
)


def environment_python(directory, windowed=False):
    if os.name == "nt":
        return directory / "Scripts" / ("pythonw.exe" if windowed else "python.exe")
    return directory / "bin" / "python"


def prepare_runtime(root):
    environment = root / ".venv-play"
    python = environment_python(environment)
    if not python.is_file():
        print("第一次使用，正在准备播放环境，请稍等……", flush=True)
        venv.EnvBuilder(with_pip=True).create(environment)
    check = subprocess.run([str(python), "-c", PROBE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if check.returncode:
        print("正在准备动画需要的组件。首次需要联网，之后可离线观看。", flush=True)
        with (environment / "setup.log").open("w", encoding="utf-8") as log:
            subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check",
                            "-r", str(root / "requirements.txt")], stdout=log, stderr=subprocess.STDOUT, check=True)
        check = subprocess.run([str(python), "-c", PROBE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if check.returncode:
            raise RuntimeError("播放环境未准备好，请确认 Python 包含 Tkinter。")
    return environment


def main(argv=None):
    if sys.version_info < (3, 10):
        print("这个源码入口需要 Python 3.10 或更新版本。普通用户请直接下载免安装版：\n" + RELEASES_URL)
        return 1
    try:
        environment = prepare_runtime(ROOT)
        python = environment_python(environment, windowed=True)
        if not python.is_file():
            python = environment_python(environment)
        subprocess.Popen([str(python), str(ROOT / "desktop.py"), *(sys.argv[1:] if argv is None else argv)], cwd=ROOT)
        return 0
    except Exception:
        print("首次准备没有完成。请连接网络后重试，或直接下载免安装版：\n" + RELEASES_URL)
        print("准备记录位于：" + str(ROOT / ".venv-play" / "setup.log"))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
