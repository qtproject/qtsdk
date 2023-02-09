rem set up running Qt Creator

set BasePath=%cd%
set ScriptPath=%~dp0

rem First argument is msvc_version (2019) and the second argument is the bitness (x86_64 / x86)
call "C:\Program Files (x86)\Microsoft Visual Studio\%1\Professional\VC\Auxiliary\Build\vcvarsall.bat" %2

set PATH=%BasePath%\qt\lib;%BasePath%\qt\bin;%BasePath%\qtcreator_install\bin;%BasePath%\debugview;%PATH%
set PATH=%PATH%;%BasePath%\logs\

rem set up run_batch_files.py
set QTC_CLANGD_CONFIG_LOG_DIR=%BasePath%\logs
set QTC_CLANGD_CONFIG_SETTINGS_DIR=%BasePath%\qtc-settings
set QTC_CLANGD_COMPLETION_RESULTS=0
set QTC_CLANGD=%BasePath%\libclang-training\bin\clangd.exe

rem run run_batch_files.py
set
echo
echo --- Running run_batch_files.py ----
call python.exe %ScriptPath%\run_batch_files.py
