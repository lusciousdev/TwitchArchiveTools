@echo off

set INPUTFILE=%~1

if "%INPUTFILE%"=="" (
  echo "No path provided."
  exit /b -1
)

set OUTPUTFILE=%~2

if "%OUTPUTFILE%"=="" (
  echo "No output provided."
  exit /b -1
)

set CRF=%~3

if "%CRF%"=="" (
  set CRF=24
)

ffmpeg -i "%INPUTFILE%" -map 0:a -map 0:v -vcodec libx265 -crf %CRF% "%OUTPUTFILE%"