@echo off

for %%i in (".\*.mp4") do (
  %~dp0/compress_video.bat %%i %%i.compressed.mp4 26
)