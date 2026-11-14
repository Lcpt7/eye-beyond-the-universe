#requires -Version 7.2
[CmdletBinding()]
param(
    [switch] $FullScreen,
    [switch] $Once,
    [ValidateRange(12, 60)] [int] $Fps = 24,
    [ValidateRange(9, 24)] [int] $FontSize = 12,
    [ValidateRange(0, 144)] [double] $StartAt = 0,
    [ValidateRange(0.1, 8)] [double] $Speed = 1
)
$ErrorActionPreference = 'Stop'
$python = Get-Command python -ErrorAction Stop
$arguments = @((Join-Path $PSScriptRoot 'beyond.py'), '--fps', $Fps, '--font-size', $FontSize, '--seek', $StartAt, '--speed', $Speed)
if ($FullScreen) { $arguments += '--fullscreen' }
if ($Once) { $arguments += '--once' }
& $python.Source @arguments
if ($LASTEXITCODE -ne 0) { throw "瞳界·星渊退出，代码 $LASTEXITCODE。" }
