/****************************************************************************
**
** Copyright (C) 2015 The Qt Company Ltd.
** Contact: http://www.qt.io/licensing/
**
** This file is part of the release tools of the Qt Toolkit.
**
** $QT_BEGIN_LICENSE:LGPL21$
** Commercial License Usage
** Licensees holding valid commercial Qt licenses may use this file in
** accordance with the commercial license agreement provided with the
** Software or, alternatively, in accordance with the terms contained in
** a written agreement between you and The Qt Company. For licensing terms
** and conditions see http://www.qt.io/terms-conditions. For further
** information use the contact form at http://www.qt.io/contact-us.
**
** GNU Lesser General Public License Usage
** Alternatively, this file may be used under the terms of the GNU Lesser
** General Public License version 2.1 or version 3 as published by the Free
** Software Foundation and appearing in the file LICENSE.LGPLv21 and
** LICENSE.LGPLv3 included in the packaging of this file. Please review the
** following information to ensure the GNU Lesser General Public License
** requirements will be met: https://www.gnu.org/licenses/lgpl.html and
** http://www.gnu.org/licenses/old-licenses/lgpl-2.1.html.
**
** As a special exception, The Qt Company gives you certain additional
** rights. These rights are described in The Qt Company LGPL Exception
** version 1.1, included in the file LGPL_EXCEPTION.txt in this package.
**
** $QT_END_LICENSE$
**
****************************************************************************/

// constructor
function Component()
{
}

Component.prototype.beginInstallation = function()
{
    installer.setValue(component.name + "_qtpath", "@TargetDir@" + "%TARGET_INSTALL_DIR%");
}

function createShortcuts()
{
    var qtStringVersion = "5.6";
    // Create a batch file with the development environment
    var component_root_path = installer.value("TargetDir") + "%TARGET_INSTALL_DIR%";
    component_root_path = component_root_path.replace(/\//g, "\\");

    var batchFileName = component_root_path + "\\" + "bin" + "\\" + "qtenv2.bat";
    var contentString = "echo off\r\n";
    contentString += "echo Setting up environment for Qt usage...\r\n";
    contentString += "set PATH="  + component_root_path + "\\bin;%PATH%\r\n";
    contentString += "cd /D " + component_root_path + "\r\n";
    contentString += "echo Remember to call vcvarsall.bat to complete environment setup!\r\n";
    // Dump batch file
    component.addOperation("AppendFile", batchFileName, contentString);

    var windir = installer.environmentVariable("WINDIR");
    if (windir == "") {
        QMessageBox["warning"]( "Error" , "Error", "Could not find windows installation directory");
        return;
    }

    var cmdLocation = windir + "\\system32\\cmd.exe";
    component.addOperation( "CreateShortcut",
                            cmdLocation,
                            "@StartMenuDir@/" + qtStringVersion + "/MSVC 2013 (32-bit)/Qt " + qtStringVersion + " 32-bit for Windows Phone x86 (MSVC 2013).lnk",
                            "/A /Q /K " + batchFileName);
}

Component.prototype.createOperations = function()
{
    component.createOperations();

    if (installer.value("os") == "win") {
        try {
            var qtPath = "@TargetDir@" + "%TARGET_INSTALL_DIR%";
            var qmakeBinary = "@TargetDir@" + "%TARGET_INSTALL_DIR%/bin/qmake.exe";
            addInitQtPatchOperation(component, "windows", qtPath, qmakeBinary, "qt5");

            // Create a batch file and shortcuts with the development environment
            createShortcuts();

            if (installer.value("SDKToolBinary") == "")
                return;

            component.addOperation("Execute",
                                   ["@SDKToolBinary@", "addQt",
                                    "--id", component.name,
                                    "--name", "Qt %{Qt:Version} for Windows Phone x86 (Emulator)",
                                    "--type", "WinRt.QtVersion.WindowsPhone",
                                    "--qmake", qmakeBinary,
                                    "UNDOEXECUTE",
                                    "@SDKToolBinary@", "rmQt", "--id", component.name]);

            var kitName = component.name + "_kit";
            component.addOperation("Execute",
                                   ["@SDKToolBinary@", "addKit",
                                    "--id", kitName,
                                    "--name", "Qt %{Qt:Version} for Windows Phone x86 MSVC2013 32bit (Emulator)",
                                    "--toolchain", "x86-windows-msvc2013-pe-32bit",
                                    "--qt", component.name,
                                    "--devicetype", "WinRt.Device.Emulator",
                                    "UNDOEXECUTE",
                                    "@SDKToolBinary@", "rmKit", "--id", kitName]);

            // patch/register docs and examples
            var installationPath = installer.value("TargetDir") + "%TARGET_INSTALL_DIR%";
            print("Register documentation and examples for: " + installationPath);
            patchQtExamplesAndDoc(component, installationPath, "Qt-5.6");

            // patch qt edition
            var qconfigFile = qtPath + "/mkspecs/qconfig.pri";
            component.addOperation("LineReplace", qconfigFile, "QT_EDITION =", "QT_EDITION = OpenSource");

        } catch( e ) {
            print( e );
        }
        if (installer.value("os") == "win") {
            var settingsFile = installer.value("QtCreatorInstallerSettingsFile");
            if (settingsFile == "")
                return;
            component.addOperation("Settings", "path="+settingsFile, "method=add_array_value",
            "key=Plugins/ForceEnabled", "value=WinRt");
        }
    }
}

