"""Double-click entry point with friendly errors and a packaged-app self-check."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import traceback
from types import SimpleNamespace

from app_info import APP_NAME, VERSION


def error_log_path():
    base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    return base / "EyeBeyond" / "startup-error.log"


def show_startup_error(error):
    log_path = error_log_path()
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(datetime.now().isoformat() + "\n" + traceback.format_exc(), encoding="utf-8")
        details = f"\n\n如果仍无法播放，可把这个日志文件发给维护者：\n{log_path}"
    except OSError:
        details = f"\n\n错误信息：{error}"
    message = "暂时没能打开动画，请关闭后重新打开。\n也可以重新下载并解压免安装版，再双击主程序。" + details
    try:
        from tkinter import messagebox
        messagebox.showerror(APP_NAME, message)
    except Exception:
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, APP_NAME, 0x10)
        elif sys.stderr:
            print(message, file=sys.stderr)


def self_test(report_path):
    """Exercise bundled NumPy, Tcl/Tk, real text items and button commands offline."""
    report = {"app": APP_NAME, "version": VERSION, "frozen": bool(getattr(sys, "frozen", False))}
    player = None
    try:
        import numpy as np
        import tkinter as tk
        from beyond import Film
        from beyond_field import Universe, DURATION

        field = Universe(96, 36)
        first = field.sample(0).text
        for t in (10, 30, 46, 63, 80, 96, 121, 132):
            frame = field.sample(t)
            if not np.isfinite(field.light).all() or frame.glyphs.shape != (36, 96):
                raise RuntimeError("Character generation self-check failed")
        if field.sample(DURATION).text != first or first.strip():
            raise RuntimeError("Loop endpoints are not black")

        args = SimpleNamespace(fullscreen=False, font_size=12, seek=10., fps=24, speed=1.,
                               still=None, once=False, max_seconds=1.0, no_text=False,
                               diagnostics=None, hidden=True)
        player = Film(args)
        player.fit()
        types = sorted({player.text.type(item) for item in player.text.find_all()})
        if types != ["text"]:
            raise RuntimeError("The canvas contains non-text drawing items")
        player.buttons["pause"].invoke()
        if not player.paused or player.buttons["pause"].cget("text") != "继续":
            raise RuntimeError("Pause button did not update")
        player.buttons["pause"].invoke()
        player.buttons["help"].invoke()
        if not player.help:
            raise RuntimeError("Help button did not update")
        player.buttons["help"].invoke()
        player.buttons["restart"].invoke()
        if player.position != 0:
            raise RuntimeError("Restart button did not reset playback")
        report.update(python=sys.version.split()[0], numpy=np.__version__, tk=tk.TkVersion,
                      canvasItemTypes=types, controls=list(player.buttons), loopEndpoints="black")
        player.run()
        if player.frames == 0:
            raise RuntimeError("The Tk event loop did not draw a frame")
        report.update(status="passed", frames=player.frames)
        code = 0
    except Exception:
        report.update(status="failed", error=traceback.format_exc())
        if player is not None and not player.stopped:
            player.root.destroy()
        code = 1
    if report_path:
        report_path = Path(report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if sys.stdout:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in argv:
        parser = argparse.ArgumentParser()
        parser.add_argument("--self-test", action="store_true")
        parser.add_argument("--report", type=Path)
        return self_test(parser.parse_args(argv).report)
    try:
        from beyond import main as play
        # Keep the existing command-line interface available for developers.
        previous = sys.argv
        try:
            sys.argv = [previous[0], *argv]
            play()
        finally:
            sys.argv = previous
        return 0
    except Exception as error:
        show_startup_error(error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
