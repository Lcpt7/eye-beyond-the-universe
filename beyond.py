"""瞳界 · 星渊 — a real-time, text-only cinematic loop.

Tk Canvas renders fixed-position color layers of monospaced ASCII text only.
No images, geometric drawing items, block glyphs, shaders, or video are displayed.
"""
from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime
import json
import math
from pathlib import Path
import sys
import time
import traceback

import numpy as np
from beyond_field import DURATION, PALETTE, Universe


def write_json(path, value):
    if path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)


def colored_lines(frame):
    """Pack character-exact row layers in NumPy, avoiding Python per-glyph work."""
    columns = frame.glyphs.shape[1]
    groups = frame.colors//4
    mask = groups[:, None, :] == np.arange(8)[None, :, None]
    layers = np.where(mask, frame.glyphs[:, None, :], " ")
    packed = layers.view(f"U{columns}").reshape(-1).tolist()
    return [line.rstrip() for line in packed]


class FrameTimings:
    """Whole-session means with a bounded window for the 95th percentile."""

    def __init__(self, capacity=7200):
        self.recent_fields = deque(maxlen=capacity)
        self.count = 0
        self.field_total = 0.
        self.paint_total = 0.

    def record(self, field_ms, paint_ms):
        self.recent_fields.append(field_ms)
        self.count += 1
        self.field_total += field_ms
        self.paint_total += paint_ms

    def summary(self):
        return {
            "meanFieldMs": round(self.field_total/self.count, 3) if self.count else 0,
            "p95FieldMs": round(float(np.percentile(self.recent_fields, 95)), 3) if self.count else 0,
            "meanTextUpdateMs": round(self.paint_total/self.count, 3) if self.count else 0,
            "fieldSampleWindowFrames": len(self.recent_fields),
        }


class Film:
    def __init__(self, args):
        import tkinter as tk
        import tkinter.font as tkfont
        self.tk, self.tkfont, self.args = tk, tkfont, args
        if sys.platform == "win32":
            import ctypes
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except (AttributeError, OSError):
                pass
        self.root = tk.Tk()
        if getattr(args, "hidden", False):
            self.root.withdraw()
        self.root.title("瞳界 · 星渊 | EYE → BEYOND THE UNIVERSE")
        self.root.configure(background="#000000")
        width = min(1360, self.root.winfo_screenwidth()-60)
        height = min(860, self.root.winfo_screenheight()-100)
        self.root.geometry(f"{width}x{height}+24+24")
        self.root.minsize(720, 440)
        self.root.attributes("-fullscreen", args.fullscreen)
        self.font = tkfont.Font(family="Consolas", size=-args.font_size)
        self.text = tk.Canvas(self.root, background="black", borderwidth=0, highlightthickness=0,
                              cursor="arrow", takefocus=False)
        self.layer_shades = (3, 7, 11, 15, 19, 23, 27, 31)
        self.items = []
        self.previous_runs = []
        self.heading = tk.Label(self.root, bg="black", fg="#c6bedb", font=("Microsoft YaHei UI", 13), borderwidth=0)
        self.caption = tk.Label(self.root, bg="black", fg="#9488af", font=("Microsoft YaHei UI", 10), borderwidth=0)
        self.heading.place(relx=.5, y=24, anchor="n")
        self.caption.place(relx=.5, rely=1., y=-80, anchor="s")
        self.build_controls()
        self.root.update_idletasks()
        self.universe = None
        self.grid_shape = None
        self.resize_pending = True
        self.position = args.seek
        self.paused = False
        self.help = False
        self.fullscreen = args.fullscreen
        self.stopped = False
        self.failure = None
        self.frames = 0
        self.cycles = 0
        self.timings = FrameTimings()
        self.started = self.previous = time.perf_counter()
        self.last_report = self.started
        self.report = {"title": "瞳界·星渊", "python": sys.version.split()[0], "numpy": np.__version__,
                       "tk": tk.TkVersion, "renderer": "Tk Canvas / text items exclusively",
                       "started": datetime.now().isoformat(timespec="seconds"), "targetFps": args.fps}
        self.root.bind("<Configure>", self.resize)
        self.root.bind("<space>", self.keyboard_pause)
        self.root.bind("<Left>", lambda e: self.seek(-5))
        self.root.bind("<Right>", lambda e: self.seek(5))
        self.root.bind("<Home>", lambda e: self.restart())
        self.root.bind("<r>", lambda e: self.restart())
        self.root.bind("<h>", lambda e: self.toggle_help())
        self.root.bind("<F1>", lambda e: self.toggle_help())
        self.root.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.root.bind("<Escape>", lambda e: self.close("user-exit"))
        self.root.bind("<q>", lambda e: self.close("user-exit"))
        self.root.protocol("WM_DELETE_WINDOW", lambda: self.close("user-exit"))
        self.root.report_callback_exception = self.callback_error
        self.root.after(20, self.step)
        self.root.focus_set()

    def build_controls(self):
        """Visible, keyboard-focusable controls for viewers who do not know hotkeys."""
        self.controls = self.tk.Frame(self.root, bg="black")
        self.controls.place(relx=.5, rely=1., y=-16, anchor="s")
        self.buttons = {}
        actions = (
            ("pause", "暂停", self.toggle_pause),
            ("restart", "重新播放", self.restart),
            ("fullscreen", "退出全屏" if self.args.fullscreen else "全屏", self.toggle_fullscreen),
            ("help", "操作说明", self.toggle_help),
            ("exit", "退出", lambda: self.close("user-exit")),
        )
        for name, title, command in actions:
            button = self.tk.Button(
                self.controls, text=title, command=command, font=("Microsoft YaHei UI", 10),
                fg="#e2d9ed", bg="#20132c", activeforeground="#ffffff", activebackground="#402a54",
                relief="flat", borderwidth=0, padx=14, pady=10, cursor="hand2", takefocus=True,
                highlightthickness=1, highlightbackground="#392744", highlightcolor="#d6b8f4",
            )
            button.pack(side="left", padx=5)
            self.buttons[name] = button

    def keyboard_pause(self, event):
        # Space activates a focused button through Tk's native binding. Do not
        # also pause playback when someone uses Space on another control.
        if event.widget.winfo_class() in ("Button", "TButton"):
            return None
        return self.toggle_pause()

    def resize(self, event):
        if event.widget is self.root:
            self.resize_pending = True

    def fit(self):
        effective_font = max(self.args.font_size, math.ceil((self.root.winfo_width()-32)/(220*.60)))
        self.font.configure(size=-effective_font)
        cell_w = self.font.measure("M")
        cell_h = self.font.metrics("linespace")
        columns = max(48, min(300, (self.root.winfo_width()-32)//cell_w))
        rows = max(24, min(100, (self.root.winfo_height()-160)//cell_h))
        rows = max(24, min(rows, int(columns*cell_w/cell_h/1.70)))
        layout = columns, rows, cell_w, cell_h
        if layout != self.grid_shape:
            self.grid_shape = layout
            self.universe = Universe(columns, rows, cell_w/cell_h)
            self.report.update(columns=columns, rows=rows, font="Consolas", fontPixels=effective_font)
            self.text.delete("all")
            self.items = []
            for y in range(rows):
                for shade in self.layer_shades:
                    item = self.text.create_text(0, y*cell_h, text="", fill=PALETTE[shade],
                                                font=self.font, anchor="nw")
                    self.items.append(item)
            self.previous_runs = [None]*len(self.items)
            self.report["canvasItemCount"] = len(self.items)
            self.report["canvasItemTypes"] = sorted({self.text.type(item) for item in self.items})
        width, height = columns*cell_w, rows*cell_h
        self.text.place(x=(self.root.winfo_width()-width)//2, y=(self.root.winfo_height()-height)//2-22,
                        width=width+2, height=height+2)
        self.resize_pending = False

    def paint(self, frame):
        commands = []
        # Eight sparse text layers per row retain per-character color, without
        # thousands of individual drawing items or a per-frame Text layout.
        for index, run in enumerate(colored_lines(frame)):
            if run != self.previous_runs[index]:
                # Glyphs come from a closed alphabet without Tcl quoting chars.
                commands.append(f"{self.text._w} itemconfigure {self.items[index]} -text {{{run}}}")
                self.previous_runs[index] = run
        if commands:
            self.text.tk.eval(";".join(commands))
        heading_color = "#%02x%02x%02x" % tuple(int(c*frame.heading_alpha) for c in (198, 190, 219))
        self.heading.configure(text="" if self.args.no_text else frame.heading, fg=heading_color)
        caption = frame.caption
        alpha = frame.caption_alpha
        if self.help:
            caption = "点击下方按钮即可操作。空格暂停，左右方向键穿梭，Esc 退出。"
            alpha = .85
        elif not caption and self.position < 5:
            caption = "约 2 分 24 秒，自动循环。随时可点击下方按钮暂停或退出。"
            alpha = .7
        caption_color = "#%02x%02x%02x" % tuple(int(c*alpha) for c in (164, 151, 191))
        self.caption.configure(text=caption if self.help or not self.args.no_text else "", fg=caption_color)

    def step(self):
        if self.stopped:
            return
        now = time.perf_counter()
        dt, self.previous = now-self.previous, now
        if not self.paused and self.args.still is None:
            self.position += dt*self.args.speed
        if self.args.max_seconds and now-self.started >= self.args.max_seconds:
            self.close("time-limit")
            return
        if self.position >= DURATION:
            if self.args.once:
                self.close("complete")
                return
            self.cycles += int(self.position//DURATION)
            self.position %= DURATION
        self.position = max(0., self.position)
        if self.resize_pending:
            self.fit()
        t = self.args.still if self.args.still is not None else self.position
        begin = time.perf_counter()
        frame = self.universe.sample(t)
        rendered = time.perf_counter()
        self.paint(frame)
        painted = time.perf_counter()
        self.timings.record((rendered-begin)*1000, (painted-rendered)*1000)
        self.frames += 1
        if now-self.last_report > 2:
            self.save_report("playing")
            self.last_report = now
        remaining = 1/self.args.fps - (time.perf_counter()-now)
        self.root.after(max(1, round(remaining*1000)), self.step)

    def toggle_pause(self, event=None):
        self.paused = not self.paused
        self.buttons["pause"].configure(text="继续" if self.paused else "暂停")
        self.report["pauseToggles"] = self.report.get("pauseToggles", 0)+1
        return "break"

    def seek(self, delta):
        self.position = float(np.clip(self.position+delta, 0., DURATION-.01))
        if self.args.still is not None:
            self.args.still = float(np.clip(self.args.still+delta, 0., DURATION))
        self.report["seekCount"] = self.report.get("seekCount", 0)+1
        return "break"

    def restart(self):
        self.position = 0.
        self.args.still = None
        self.previous = time.perf_counter()
        self.report["restarts"] = self.report.get("restarts", 0)+1

    def toggle_help(self):
        self.help = not self.help
        self.buttons["help"].configure(text="收起说明" if self.help else "操作说明")

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)
        self.buttons["fullscreen"].configure(text="退出全屏" if self.fullscreen else "全屏")
        self.resize_pending = True

    def save_report(self, status, error=None):
        elapsed = time.perf_counter()-self.started
        self.report.update(status=status, frames=self.frames, elapsedSeconds=round(elapsed, 3),
                           actualFps=round(self.frames/elapsed, 2) if elapsed else 0,
                           position=round(self.position, 3), cycles=self.cycles, paused=self.paused,
                           fullScreen=self.fullscreen, error=error, **self.timings.summary())
        if self.args.diagnostics:
            write_json(self.args.diagnostics, self.report)

    def callback_error(self, exc_type, exc_value, exc_traceback):
        error = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        self.close("error", error)

    def close(self, reason, error=None):
        if not self.stopped:
            self.stopped = True
            self.failure = error
            try:
                self.save_report(reason, error)
            except Exception as report_error:
                if self.failure is None:
                    self.failure = f"Cannot save diagnostics: {report_error}"
                raise
            finally:
                self.root.destroy()

    def run(self):
        self.root.mainloop()
        if self.failure is not None:
            raise RuntimeError(self.failure)


def parse_args():
    parser = argparse.ArgumentParser(description="瞳界·星渊 — 实时字符电影")
    parser.add_argument("--fps", type=int, choices=range(12, 61), default=24)
    parser.add_argument("--font-size", type=int, choices=range(9, 25), default=12)
    parser.add_argument("--speed", type=float, default=1.)
    parser.add_argument("--seek", type=float, default=0.)
    parser.add_argument("--still", type=float)
    parser.add_argument("--max-seconds", type=float, default=0.)
    parser.add_argument("--fullscreen", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--no-text", action="store_true")
    parser.add_argument("--diagnostics", type=Path)
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--export-text", type=Path)
    parser.add_argument("--frames", type=int, default=144)
    args = parser.parse_args()
    if (not all(math.isfinite(x) for x in (args.speed, args.seek, args.max_seconds))
            or not 0 < args.speed <= 8 or not 0 <= args.seek <= DURATION or args.max_seconds < 0 or args.frames < 1):
        parser.error("speed must be in (0,8], seek in [0,144], and times/frames must be finite and non-negative")
    if args.still is not None and (not math.isfinite(args.still) or not 0 <= args.still <= DURATION):
        parser.error("still must be between 0 and 144 seconds")
    return args


def main():
    args = parse_args()
    if args.export_text:
        field = Universe(144, 56)
        frame = field.sample(args.still if args.still is not None else args.seek)
        args.export_text.parent.mkdir(parents=True, exist_ok=True)
        args.export_text.write_text(frame.text, encoding="utf-8")
        print(frame.text)
    elif args.benchmark:
        field = Universe()
        costs = []
        for t in np.linspace(0, DURATION, args.frames):
            tick = time.perf_counter()
            frame = field.sample(t)
            frame.text
            costs.append((time.perf_counter()-tick)*1000)
        report = {"frames": args.frames, "columns": field.columns, "rows": field.rows,
                  "meanFieldMs": round(float(np.mean(costs)), 3), "p95FieldMs": round(float(np.percentile(costs, 95)), 3),
                  "output": "headless character generation, excludes Tk presentation"}
        write_json(args.diagnostics, report)
        print(json.dumps(report, indent=2))
    else:
        Film(args).run()


if __name__ == "__main__":
    main()
