:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
::
:: Copyright (C) 2014 Digia Plc and/or its subsidiary(-ies).
:: Contact: http://www.qt-project.org/legal
::
:: This file is part of the tools applications of the Qt Toolkit.
::
:: $QT_BEGIN_LICENSE:LGPL$
:: Commercial License Usage
:: Licensees holding valid commercial Qt licenses may use this file in
:: accordance with the commercial license agreement provided with the
:: Software or, alternatively, in accordance with the terms contained in
:: a written agreement between you and Digia.  For licensing terms and
:: conditions see http://qt.digia.com/licensing.  For further information
:: use the contact form at http://qt.digia.com/contact-us.
::
:: GNU Lesser General Public License Usage
:: Alternatively, this file may be used under the terms of the GNU Lesser
:: General Public License version 2.1 as published by the Free Software
:: Foundation and appearing in the file LICENSE.LGPL included in the
:: packaging of this file.  Please review the following information to
:: ensure the GNU Lesser General Public License version 2.1 requirements
:: will be met: http://www.gnu.org/licenses/old-licenses/lgpl-2.1.html.
::
:: In addition, as a special exception, Digia gives you certain additional
:: rights.  These rights are described in the Digia Qt LGPL Exception
:: version 1.1, included in the file LGPL_EXCEPTION.txt in this package.
::
:: GNU General Public License Usage
:: Alternatively, this file may be used under the terms of the GNU
:: General Public License version 3.0 as published by the Free Software
:: Foundation and appearing in the file LICENSE.GPL included in the
:: packaging of this file.  Please review the following information to
:: ensure the GNU General Public License version 3.0 requirements will be
:: met: http://www.gnu.org/copyleft/gpl.html.
::
::
:: $QT_END_LICENSE$
::
:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

REM Set some env for Qt5 app builds

echo on

echo %cfg%|findstr /i msvc2010 >nul:
if %errorlevel%==0 (
set "PATH=c:\work\build\qtsdk\gnuwin32\bin;C:\Utils\icu32_52_1_msvc2010\bin;c:\Utils\icu32_52_1_msvc2010\lib;%PATH_MSVC2010%;%PATH%"
set "LIB=c:\Utils\icu32_52_1_msvc2010\lib;%LIB_MSVC2010%;%LIB%"
set "LIBPATH=c:\Utils\icu32_52_1_msvc2010\lib;%LIBPATH_MSVC2010%;%LIBPATH%"
set "INCLUDE=C:\Utils\icu32_52_1_msvc2010\include;%INCLUDE_MSVC2010%;%INCLUDE%"
set "NODE_VS_V=vs2010"
)

echo %cfg%|findstr /i msvc2012-Windows8-x64 >nul:
if %errorlevel%==0 (
set "PATH=c:\work\build\qtsdk\gnuwin32\bin;C:\Utils\icu64_51_1\bin;c:\Utils\icu64_51_1\lib;%PATH_MSVC2012%;%PATH%"
set "LIB=c:\Utils\icu64_51_1\lib;%LIB_MSVC2012%;%LIB%"
set "LIBPATH=c:\Utils\icu64_51_1\lib;%LIBPATH_MSVC2012%;%LIBPATH%"
set "INCLUDE=C:\Utils\icu64_51_1\include;%INCLUDE_MSVC2012%;%INCLUDE%"
set "NODE_VS_V=vs2012"
)

echo %cfg%|findstr /i msvc2012-Windows8-x86 >nul:
if %errorlevel%==0 (
set "PATH=c:\work\build\qtsdk\gnuwin32\bin;C:\Utils\icu32_51_1\bin;c:\Utils\icu32_51_1\lib;%PATH_MSVC2012%;%PATH%"
set "LIB=c:\Utils\icu32_51_1\lib;%LIB_MSVC2012%;%LIB%"
set "LIBPATH=c:\Utils\icu32_51_1\lib;%LIBPATH_MSVC2012%;%LIBPATH%"
set "INCLUDE=C:\Utils\icu32_51_1\include;%INCLUDE_MSVC2012%;%INCLUDE%"
set "NODE_VS_V=vs2012"
)

echo %cfg%|findstr /i msvc2012-Windows8.1-x86 >nul:
if %errorlevel%==0 (
set "PATH=c:\work\build\qtsdk\gnuwin32\bin;%PATH_MSVC2012%;%PATH%
set "LIB=%LIB_MSVC2012%;%LIB%"
set "LIBPATH=%LIBPATH_MSVC2012%;%LIBPATH%"
set "INCLUDE=%INCLUDE_MSVC2012%;%INCLUDE%"
set "NODE_VS_V=vs2012"
set CURL="C:\Program Files\Git\bin\curl.exe"
set RM="C:\Program Files\Git\bin\rm.exe"
set SCP="C:\Program Files\Git\bin\scp.exe"
set SSH="C:\Program Files\Git\bin\ssh.exe"
)

echo %cfg%|findstr /i msvc2013-Windows8.1-x86 >nul:
if %errorlevel%==0 (
set "PATH=c:\work\build\qtsdk\gnuwin32\bin;%PATH_MSVC2013%;!PATH!"
set "LIB=%LIB_MSVC2013%;C:!LIB!"
set "LIBPATH=%LIBPATH_MSVC2013;!LIBPATH!"
set "INCLUDE=%INCLUDE_MSVC2013%;!INCLUDE!"
set "CURL=C:\Program Files\Git\bin\curl.exe"
set RM="C:\Program Files\Git\bin\rm.exe"
set SCP="C:\Program Files\Git\bin\scp.exe"
set SSH="C:\Program Files\Git\bin\ssh.exe"
call "c:\Program Files\Microsoft Visual Studio 12.0\vc\vcvarsall.bat"
)

echo %cfg%|findstr /i win-msvc2013-Windows8.1-x64 >nul:
if %errorlevel%==0 (
set "PATH=c:\work\build\qtsdk\gnuwin32\bin;%PATH_MSVC2013%;%PATH%"
set "LIB=%LIB_MSVC2013%;%LIB%"
set "LIBPATH=%LIBPATH_MSVC2013%;%LIBPATH%"
set "INCLUDE=%INCLUDE_MSVC2013%;%INCLUDE%"
call "c:\Program Files (x86)\Microsoft Visual Studio 12.0\vc\vcvarsall.bat" amd64
)

echo %cfg%|findstr /i win-msvc2013-Windows8.1-x64_WinRT >nul:
if %errorlevel%==0 (
set "PATH=c:\windows\SysWOW64;c:\work\build\qtsdk\gnuwin32\bin;C:\utils\mysql\mysql\bin;C:\utils\postgresql\pgsql\bin;C:\Python27\;C:\Python27\Scripts;C:\Windows\System32\WindowsPowerShell\v1.0\;C:\Program Files (x86)\Git\cmd;C:\strawberry\c\bin;C:\strawberry\perl\site\bin;C:\strawberry\perl\bin;C:\Program Files\Microsoft SQL Server\110\Tools\Binn\;C:\openssl\bin;C:\Program Files (x86)\Java\jdk7\bin;C:\mingw\mingw\bin;C:\mingw48\mingw32\bin;C:\utils\jom;C:\CMake\in;C:\ruby\bin;C:\utils\sevenzip\;C:\utils\squish\squish\bin;C:\utils\squish\;C:\utils\squish\squish;C:\Program Files (x86)\Notepad++;!PATH!"
set "LIB=C:\utils\postgresql\pgsql\lib;C:\utils\mysql\mysql\lib;!LIB!"
set "LIBPATH=C:\utils\postgresql\pgsql\lib;C:\utils\mysql\mysql\lib;!LIBPATH!"
set "INCLUDE=C:\utils\postgresql\pgsql\include;C:\utils\mysql\mysql\include;!INCLUDE!"
call "c:\Program Files (x86)\Microsoft Visual Studio 12.0\vc\vcvarsall.bat" x86
)

echo %cfg%|findstr /i win-msvc2012-Windows8.1-x64_Winphone8 >nul:
if %errorlevel%==0 (
set "PATH=c:\windows\SysWOW64;c:\work\build\qtsdk\gnuwin32\bin;C:\utils\mysql\mysql\bin;C:\utils\postgresql\pgsql\bin;C:\Python27\;C:\Python27\Scripts;C:\Windows\System32\WindowsPowerShell\v1.0\;C:\Program Files (x86)\Git\cmd;C:\strawberry\c\bin;C:\strawberry\perl\site\bin;C:\strawberry\perl\bin;C:\Program Files\Microsoft SQL Server\110\Tools\Binn\;C:\openssl\bin;C:\Program Files (x86)\Java\jdk7\bin;C:\mingw\mingw\bin;C:\mingw48\mingw32\bin;C:\Utils\icu32_52_1_mingw482\bin;C:\utils\jom;C:\CMake\in;C:\ruby\bin;C:\utils\sevenzip\;C:\utils\squish\squish\bin;C:\utils\squish\;C:\utils\squish\squish;C:\Program Files (x86)\Notepad++;!PATH!"
set "LIB=C:\utils\postgresql\pgsql\lib;C:\utils\mysql\mysql\lib;!LIB!"
set "LIBPATH=C:\utils\postgresql\pgsql\lib;C:\utils\mysql\mysql\lib;!LIBPATH!"
set "INCLUDE=C:\utils\postgresql\pgsql\include;C:\utils\mysql\mysql\include;!INCLUDE!"
call "c:\Program Files (x86)\Microsoft Visual Studio 12.0\vc\vcvarsall.bat" x86
)

echo %cfg%|findstr /i ndroid >nul:
if %errorlevel%==0 (
set "EXTRA_QT_CONFIGURE_OPTIONS=-D QT_EVAL"
)

echo %cfg%|findstr /i Android >nul:
if %errorlevel%==0 (
set "PATH=c:\work\build\qtsdk\gnuwin32\bin;c:\mingw482\mingw32\bin;%PATH%;C:\Utils\icu32_51_1_mingw48\bin;C:\Utils\icu32_51_1_mingw48\lib;C:\Utils\pgsql\bin;C:\temp\openssl-android-master\openssl-android-master\bin"
set "LIB=C:\Utils\icu32_51_1_mingw482\lib;%LIB%;C:\Utils\pgsql\lib;C:\temp\opensll-android-master\openssl-android-master\lib"
set "INCLUDE=%INCLUDE%;C:\Utils\icu32_51_1_mingw48\include;C:\Utils\pgsql\include;C:\temp\openssl-android-master\openssl-android-master\include;C:\mingw482\mingw32\include"
set QTDIR=
set ANDROID_BUILD_TOOLS_REVISION=android-4.2.2
set ANDROID_NDK_HOST=windows
set ANDROID_NDK_PLATFORM=android-9
set ANDROID_NDK_ROOT=c:\Utils\android\ndk
set ANDROID_NDK_TOOLCHAIN_VERSION=4.8
set ANDROID_SDK_ROOT=c:\Utils\android\sdk\sdk
set NODE_ARCH=32
set ANDROID_NDK_HOME=c:\Utils\android\ndk
set ANDROID_SDK_HOME=c:\Utils\android\sdk\sdk
)

echo %cfg%|findstr /i Android-armv7 >nul:
if %errorlevel%==0 (
set ANDROID_TARGET_ARCH=armeabi-v7a
set RELEASE_BUILD_QT_CONFIGURE_OPTIONS_FILE=configure_android_armv7_enterprise
)

echo %cfg%|findstr /i Android-armv5 >nul:
if %errorlevel%==0 (
set ANDROID_TARGET_ARCH=armeabi
set RELEASE_BUILD_QT_CONFIGURE_OPTIONS_FILE=configure_android_armv5_enterprise
)

echo %cfg%|findstr /i Android-x86 >nul:
if %errorlevel%==0 (
set ANDROID_TARGET_ARCH=x86
set RELEASE_BUILD_QT_CONFIGURE_OPTIONS_FILE=configure_android_x86_enterprise
)

echo %cfg%|findstr /i OpenGL >nul:
if %errorlevel%==0 (
set RELEASE_BUILD_QT_CONFIGURE_OPTIONS_FILE=configure_win_opengl_enterprise
)

echo %cfg%|findstr /i ANGLE >nul:
if %errorlevel%==0 (
set RELEASE_BUILD_QT_CONFIGURE_OPTIONS_FILE=configure_win_enterprise
)

echo %cfg%|findstr /i WinRT >nul:
if %errorlevel%==0 (
set RELEASE_BUILD_QT_CONFIGURE_OPTIONS_FILE=configure_winrt_x64_enterprise
)

echo %cfg%|findstr /i Winphone8_arm >nul:
if %errorlevel%==0 (
set RELEASE_BUILD_QT_CONFIGURE_OPTIONS_FILE=configure_winphone_arm_enterprise
)

echo %cfg%|findstr /i winphone8_x86 >nul:
if %errorlevel%==0 (
set RELEASE_BUILD_QT_CONFIGURE_OPTIONS_FILE=configure_winphone_x86_enterprise
)


echo %cfg%|findstr /i win-MinGW4.8-Windows7-x86_OpenGL >nul:
if %errorlevel%==0 (
set "PATH=c:\work\build\qtsdk\gnuwin32\bin;%PATH_MINGW48%;C:\Utils\icu32_51_1_mingw48\bin;C:\Utils\icu32_51_1_mingw48\lib;%PATH%;C:\openssl\bin"
set "LIB=C:\mingw48\mingw32\lib;;C:\Utils\icu32_51_1_mingw48\lib;%LIB%;C:\opensll\lib"
set "INCLUDE=%INCLUDE%;C:\mingw48\mingw32\include;C:\Utils\icu32_51_1_mingw48\include;C:\openssl\include"
set QTDIR=
set "NODE_ARCH=32"
)

echo %cfg%|findstr /i win-MinGW4.8.2-Windows7-x86_OpenGL >nul:
if %errorlevel%==0 (
set "PATH=c:\work\build\qtsdk\gnuwin32\bin;c:\mingw482\mingw32\bin;C:\Utils\icu32_52_1_mingw482\bin;C:\Utils\icu32_52_1_mingw482\lib;%PATH%;C:\openssl\bin"
set "LIB=C:\mingw482\mingw32\lib;;C:\Utils\icu32_52_1_mingw482\lib;%LIB%;C:\opensll\lib"
set "INCLUDE=%INCLUDE%;C:\mingw482\mingw32\include;C:\Utils\icu32_52_1_mingw482\include;C:\openssl\include"
set QTDIR=
set "NODE_ARCH=32"
)

set "ZIP_TOOL_PATH=C:\utils\sevenzip"
set 7Z_TOOL_PATH="C:\utils\sevenzip"

set GIT_TOOL_PATH="C:\Program Files\git\cmd"
echo %cfg%|findstr /i x64 >nul:
if %errorlevel%==0 (
set GIT_TOOL_PATH="C:\Program Files (x86)\git\cmd"
)
set QT5_APPLICATION_BUILD_CMD="jom"
set QT5_APPLICATION_INSTALL_CMD="nmake -j1"

echo %cfg%|findstr /i win-MinGW4.8.2-Windows7-x86_OpenGL >nul:
if %errorlevel%==0 (
  set QT5_APPLICATION_BUILD_CMD="mingw32-make -j1"
  set QT5_APPLICATION_INSTALL_CMD="mingw32-make -j1"
)

echo %cfg%|findstr /i Android >nul:
if %errorlevel%==0 (
  set QT5_APPLICATION_BUILD_CMD="mingw32-make -j1"
  set QT5_APPLICATION_INSTALL_CMD="mingw32-make -j1"
)


echo "Qt5 essentials lib: %QT5_ESSENTIALS_LIB_PACKAGE_URI%"
echo "Qt5 addons lib: %QT5_ADDONS_LIB_PACKAGE_URI%"
echo "Qt5 application build cmd: %QT5_APPLICATION_BUILD_CMD%"
echo "Qt5 application install cmd: %QT5_APPLICATION_INSTALL_CMD%"


