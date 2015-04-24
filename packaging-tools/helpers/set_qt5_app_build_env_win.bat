:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
::
:: Copyright (C) 2015 The Qt Company Ltd.
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

set "ZIP_TOOL_PATH=C:\utils\sevenzip"
set 7Z_TOOL_PATH="C:\utils\sevenzip"

set GIT_TOOL_PATH="C:\Program Files\git\cmd"
echo %cfg%|findstr /i x64 >nul:
if %errorlevel%==0 (
set GIT_TOOL_PATH="C:\Program Files (x86)\git\cmd"
)
set QT5_APPLICATION_BUILD_CMD="jom"
set QT5_APPLICATION_INSTALL_CMD="jom -j1"

echo %cfg%|findstr /i MinGW >nul:
if %errorlevel%==0 (
  set QT5_APPLICATION_BUILD_CMD="mingw32-make -j1"
  set QT5_APPLICATION_INSTALL_CMD="mingw32-make -j1"
)

echo %cfg%|findstr /i Android >nul:
if %errorlevel%==0 (
  set QT5_APPLICATION_BUILD_CMD="mingw32-make -j1"
  set QT5_APPLICATION_INSTALL_CMD="mingw32-make -j1"
)

echo %cfg%|findstr /i QNX >nul:
if %errorlevel%==0 (
  set QT5_APPLICATION_BUILD_CMD="mingw32-make -j1"
  set QT5_APPLICATION_INSTALL_CMD="make -j1"
)

echo "Qt5 essentials lib: %QT5_ESSENTIALS_LIB_PACKAGE_URI%"
echo "Qt5 addons lib: %QT5_ADDONS_LIB_PACKAGE_URI%"
echo "Qt5 application build cmd: %QT5_APPLICATION_BUILD_CMD%"
echo "Qt5 application install cmd: %QT5_APPLICATION_INSTALL_CMD%"


