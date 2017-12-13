rem set up running Qt Creator

set BasePath=%cd%
set ScriptPath=%~dp0

call "C:\Program Files (x86)\Microsoft Visual Studio 14.0\VC\vcvarsall.bat" x86_amd64
set PATH=%BasePath%\qt\lib;%BasePath%\qt\bin;%BasePath%\qtcreator_build\bin;%BasePath%\debugview;%PATH%
set PATH=%PATH%;%BasePath%\logs\

rem set up runBachFiles.py
set QTC_CLANG_BATCH_CONFIG_LOG_DIR=%BasePath%\logs
set QTC_CLANG_BATCH_CONFIG_SETTINGS_DIR=%BasePath%\qtc-settings
set QTC_CLANG_BATCH_CONFIG_TARGET_LIBCLANG=%BasePath%\logs\libclang.dll
set QTC_CLANG_BATCH_CONFIG_LIBCLANGS=%BasePath%\libclang\bin\libclang.dll
set QTC_CLANG_BATCH_CONFIG_FILES=%ScriptPath%\qtc.fileTextEditorCpp.batch

rem run runBatchFiles.py
set
echo
echo --- Running runBatchFiles.py ----
call python.exe %ScriptPath%\runBatchFiles.py

