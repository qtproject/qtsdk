/****************************************************************************
**
** Copyright (C) 2014 Digia Plc and/or its subsidiary(-ies).
** Contact: http://www.qt-project.org/legal
**
** This file is part of the release tools of the Qt Toolkit.
**
** $QT_BEGIN_LICENSE:LGPL$
** Commercial License Usage
** Licensees holding valid commercial Qt licenses may use this file in
** accordance with the commercial license agreement provided with the
** Software or, alternatively, in accordance with the terms contained in
** a written agreement between you and Digia.  For licensing terms and
** conditions see http://qt.digia.com/licensing.  For further information
** use the contact form at http://qt.digia.com/contact-us.
**
** GNU Lesser General Public License Usage
** Alternatively, this file may be used under the terms of the GNU Lesser
** General Public License version 2.1 as published by the Free Software
** Foundation and appearing in the file LICENSE.LGPL included in the
** packaging of this file.  Please review the following information to
** ensure the GNU Lesser General Public License version 2.1 requirements
** will be met: http://www.gnu.org/licenses/old-licenses/lgpl-2.1.html.
**
** In addition, as a special exception, Digia gives you certain additional
** rights.  These rights are described in the Digia Qt LGPL Exception
** version 1.1, included in the file LGPL_EXCEPTION.txt in this package.
**
** GNU General Public License Usage
** Alternatively, this file may be used under the terms of the GNU
** General Public License version 3.0 as published by the Free Software
** Foundation and appearing in the file LICENSE.GPL included in the
** packaging of this file.  Please review the following information to
** ensure the GNU General Public License version 3.0 requirements will be
** met: http://www.gnu.org/copyleft/gpl.html.
**
**
** $QT_END_LICENSE$
**
****************************************************************************/


// constructor
function Component()
{
    installer.valueChanged.connect( this, Component.prototype.reactOnTargetDirChange );
    // set the default values to MINGW491_DIR
    Component.prototype.reactOnTargetDirChange("TargetDir", installer.value("TargetDir"));
}

Component.prototype.reactOnTargetDirChange = function(key, value)
{
    if (key == "TargetDir") {
        var path = value + "%TARGET_INSTALL_DIR%";
        path = path.replace(/\//g, "\\");
        installer.setValue("MINGW491_DIR", path);
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
            installer.setValue("MINGW491_TCID", tcId);
            installer.setValue("MINGW491_DBGID", dbgId);

            component.addOperation("Execute",
                                   ["{0,2}", "@SDKToolBinary@", "addTC",
                                    "--id", tcId,
                                    "--name", "MinGW 4.9.1 32bit",
                                    "--path", "@MINGW491_DIR@\\bin\\g++.exe",
                                    "--abi", "x86-windows-msys-pe-32bit",
                                    "--supportedAbis", "x86-windows-msys-pe-32bit",
                                    "UNDOEXECUTE",
                                    "@SDKToolBinary@", "rmTC", "--id", tcId]);

            component.addOperation("Execute",
                                   ["{0,2}", "@SDKToolBinary@", "addDebugger",
                                    "--id", dbgId,
                                    "--name", "GNU gdb 7.8 for MinGW 4.9.1 32bit",
                                    "--binary", "@MINGW491_DIR@\\bin\\gdb.exe",
                                    "--abis", "x86-windows-msys-pe-32bit",
                                    "--engine", "1"
                                    "UNDOEXECUTE",
                                    "@SDKToolBinary@", "rmDebugger", "--id", dbgId]);

            component.addOperation("Execute",
                                   ["{0,4}", "@SDKToolBinary@", "addKeys",
                                    "android", "MakeExtraSearchDirectory", "QString:@MINGW491_DIR@\\bin"]);
        } catch( e ) {
            print( e );
        }
    }
}
