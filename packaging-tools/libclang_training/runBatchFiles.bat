rem set up running Qt Creator

set BasePath=%cd%
set ScriptPath=%~dp0

rem First argument is msvc_version (2019) and the second argument is the bitness (x86_64 / x86)
call "C:\Program Files (x86)\Microsoft Visual Studio\%1\Professional\VC\Auxiliary\Build\vcvarsall.bat" %2

set PATH=%BasePath%\qt\lib;%BasePath%\qt\bin;%BasePath%\qtcreator_install\bin;%BasePath%\debugview;%PATH%
set PATH=%PATH%;%BasePath%\logs\

rem set up runBachFiles.py
set QTC_CLANG_BATCH_CONFIG_LOG_DIR=%BasePath%\logs
set QTC_CLANG_BATCH_CONFIG_SETTINGS_DIR=%BasePath%\qtc-settings
set QTC_CLANG_BATCH_CONFIG_TARGET_LIBCLANG=%BasePath%\logs\libclang.dll
set QTC_CLANG_BATCH_CONFIG_LIBCLANGS=%BasePath%\libclang-training\bin\libclang.dll
set QTC_CLANG_BATCH_CONFIG_FILES=%ScriptPath%\%3

rem run runBatchFiles.py
set
echo
echo --- Running runBatchFiles.py ----
call python.exe %ScriptPath%\runBatchFiles.py
