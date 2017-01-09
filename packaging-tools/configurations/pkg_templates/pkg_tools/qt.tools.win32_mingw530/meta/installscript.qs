/****************************************************************************
**
** Copyright (C) 2016 The Qt Company Ltd.
** Contact: https://www.qt.io/licensing/
**
** This file is part of the release tools of the Qt Toolkit.
**
** $QT_BEGIN_LICENSE:GPL-EXCEPT$
** Commercial License Usage
** Licensees holding valid commercial Qt licenses may use this file in
** accordance with the commercial license agreement provided with the
** Software or, alternatively, in accordance with the terms contained in
** a written agreement between you and The Qt Company. For licensing terms
** and conditions see https://www.qt.io/terms-conditions. For further
** information use the contact form at https://www.qt.io/contact-us.
**
** GNU General Public License Usage
** Alternatively, this file may be used under the terms of the GNU
** General Public License version 3 as published by the Free Software
** Foundation with exceptions as appearing in the file LICENSE.GPL3-EXCEPT
** included in the packaging of this file. Please review the following
** information to ensure the GNU General Public License requirements will
** be met: https://www.gnu.org/licenses/gpl-3.0.html.
**
** $QT_END_LICENSE$
**
****************************************************************************/


// constructor
function Component()
{
    installer.valueChanged.connect( this, Component.prototype.reactOnTargetDirChange );
    // set the default values to MINGW530_DIR
    Component.prototype.reactOnTargetDirChange("TargetDir", installer.value("TargetDir"));
}

Component.prototype.reactOnTargetDirChange = function(key, value)
{
    if (key == "TargetDir") {
        var path = value + "%TARGET_INSTALL_DIR%";
        installer.setValue("MINGW530_DIR", path.replace(/\\/g, "/"));
    }
}

Component.prototype.createOperations = function()
{
    component.createOperations();

    if (installer.value("os") == "win") {
        try {
            if (installer.value("SDKToolBinary") == "")
                return;

            var tcId = "ProjectExplorer.ToolChain.Mingw:" + component.name;
            var dbgId = "Debugger." + component.name;
            installer.setValue("MINGW530_TCID", tcId);
            installer.setValue("MINGW530_DBGID", dbgId);

            component.addOperation("Execute",
                                   ["{0,2}", "@SDKToolBinary@", "addTC",
                                    "--id", tcId + ".gcc",
                                    "--name", "MinGW 5.3.0 32bit for C",
                                    "--path", "@MINGW530_DIR@/bin/gcc.exe",
                                    "--abi", "x86-windows-msys-pe-32bit",
                                    "--language", "1",
                                    "--supportedAbis", "x86-windows-msys-pe-32bit",
                                    "UNDOEXECUTE",
                                    "@SDKToolBinary@", "rmTC", "--id", tcId + ".gcc"]);

            component.addOperation("Execute",
                                   ["{0,2}", "@SDKToolBinary@", "addTC",
                                    "--id", tcId + ".g++",
                                    "--name", "MinGW 5.3.0 32bit for C++",
                                    "--path", "@MINGW530_DIR@/bin/g++.exe",
                                    "--abi", "x86-windows-msys-pe-32bit",
                                    "--language", "2",
                                    "--supportedAbis", "x86-windows-msys-pe-32bit",
                                    "UNDOEXECUTE",
                                    "@SDKToolBinary@", "rmTC", "--id", tcId + ".g++"]);

            component.addOperation("Execute",
                                   ["{0,2}", "@SDKToolBinary@", "addDebugger",
                                    "--id", dbgId,
                                    "--name", "GNU gdb 7.10.1 for MinGW 5.3.0 32bit",
                                    "--binary", "@MINGW530_DIR@/bin/gdb.exe",
                                    "--abis", "x86-windows-msys-pe-32bit",
                                    "--engine", "1",
                                    "UNDOEXECUTE",
                                    "@SDKToolBinary@", "rmDebugger", "--id", dbgId]);

            component.addOperation("Execute",
                                   ["{0,4}", "@SDKToolBinary@", "addKeys",
                                    "android", "MakeExtraSearchDirectory", "QString:@MINGW530_DIR@/bin"]);
        } catch( e ) {
            print( e );
        }
    }
}
