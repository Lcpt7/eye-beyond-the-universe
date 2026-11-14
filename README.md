# 瞳界 · 星渊

**EYE → BEYOND THE UNIVERSE**

一段 144 秒的实时字符电影：睁眼、星辰倒影、瞳孔穿越、星云与巨型行星、黑洞、古老星门和星辰巨龙，最终万星汇聚成眼。镜头拉远，将这只眼睛纳入更大的瞳孔；外层眼睛缓缓闭合，回到开场黑暗。默认循环播放。

所有画面均实时生成。窗口只绘制 ASCII 字符和 Unicode 字幕，不使用图片、视频、预制帧、半块字符或实心像素块。

## 播放

需要 Windows、Python 3.10 或更新版本（包含 Tkinter）；使用启动脚本还需 PowerShell 7.2 或更新版本。

首次使用时，在本目录创建环境并安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

然后运行：

```powershell
.\Start-Beyond.ps1
```

全屏播放一遍：

```powershell
.\Start-Beyond.ps1 -FullScreen -Once
```

也可直接运行 `python beyond.py`。已在本机 Python 3.10.11、NumPy 1.26.4、Tk 8.6 下运行；PowerShell 只负责启动。画布会随窗口尺寸重新计算字符网格，全屏时自动调整字号以控制绘制成本。

| 按键 | 功能 |
| --- | --- |
| 空格 | 暂停 / 继续 |
| ← / → | 前后穿梭 5 秒 |
| R / Home | 从开场重播 |
| F11 | 切换全屏 |
| H | 显示 / 隐藏帮助 |
| Esc / Q | 退出 |

## 镜头与实现

详见 [STORYBOARD.md](STORYBOARD.md)。前段留出大面积黑暗，以虹膜纤维、星辰反射和一次眨眼建立凝视感。穿越后逐渐扩大尺度，星龙保持星点与稀疏连线构成的透明轮廓。结尾的星辰有明确汇聚轨迹；外层眼睑会遮住内层宇宙。

NumPy 在字符位置计算连续光场，再转换为字符疏密和银紫色阶。Tk Canvas 仅创建 `text` 项，每行分成八个颜色文字层，固定字距和行距。没有 Canvas 图形项或位图绘制。固定随机种子、连续时间和静态空间抖动避免随机闪烁。

本机的旧版归档不参与新版播放，也不包含在 GitHub 仓库中。

## 验证与调试

```powershell
python -X utf8 -m unittest discover -s tests -v
python beyond.py --benchmark --frames 144 --diagnostics proofs\benchmark.json
python beyond.py --seek 117 --once --diagnostics proofs\ending-live.json
```

`--seek` 定位到指定秒数；`--still 10` 保持一个实时生成的镜头。`--export-text proofs\frame.txt --still 10` 可导出纯文字诊断帧，诊断文件不会被读回用于播放。

`proofs` 保存本机实播帧率、字符网格尺寸、绘制项类型和错误记录。离屏基准只衡量字符生成，不代表窗口实际帧率。桌面工具目前未获准访问 pythonw 窗口，因此没有将窗口截图或直接视觉验收写成已完成。

循环播放的统计采样最多保留 7200 帧，平均耗时仍覆盖整个会话；95 分位耗时取最近的采样窗口。渲染或诊断写入失败会关闭窗口并返回非零退出码。GitHub Actions 会自动检查 Windows / NumPy 1.x 和 Linux / NumPy 2.x 下的文字生成及播放生命周期逻辑；这些检查不替代实际窗口的视觉验收。
