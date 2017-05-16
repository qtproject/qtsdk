/****************************************************************************
**
** Copyright (C) 2017 The Qt Company Ltd.
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
}

function createShortcuts()
{
    var qtStringVersion = "5.9";
    // Create a batch file with the development environment
    var component_root_path = installer.value("TargetDir") + "%TARGET_INSTALL_DIR%";
    component_root_path = component_root_path.replace(/\//g, "\\");

    var batchFileName = component_root_path + "\\" + "bin" + "\\" + "qtenv2.bat";
    var contentString = "@echo off\r\n";
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
                            "@StartMenuDir@/" + qtStringVersion + "/MSVC 2017 (64-bit)/Qt " + qtStringVersion + " 64-bit for Universal Windows Platform 32bit (MSVC 2017).lnk",
                            "/A /Q /K " + batchFileName);
}

Component.prototype.beginInstallation = function()
{
    installer.setValue(component.name + "_qtpath", "@TargetDir@" + "%TARGET_INSTALL_DIR%");
}

Component.prototype.createOperations = function()
{
    component.createOperations();

    if (installer.value("os") == "win") {
        try {
            var qtPath = "@TargetDir@" + "%TARGET_INSTALL_DIR%";
            var qmakeBinary = "@TargetDir@" + "%TARGET_INSTALL_DIR%/bin/qmake.exe";
            addInitQtPatchOperation(component, "windows", qtPath, qmakeBinary, "emb-arm-qt5");

            // Create a batch file and shortcuts with the development environment
            createShortcuts();

            if (installer.value("SDKToolBinary") == "")
                return;

            component.addOperation("Execute",
                                   ["@SDKToolBinary@", "addQt",
                                    "--id", component.name,
                                    "--name", "Qt %{Qt:Version} for UWP 32bit (MSVC 2017)",
                                    "--type", "WinRt.QtVersion.WindowsRuntime",
                                    "--qmake", qmakeBinary,
                                    "UNDOEXECUTE",
                                    "@SDKToolBinary@", "rmQt", "--id", component.name]);

            var kitName = component.name + "_kit";
            component.addOperation("Execute",
                                   ["@SDKToolBinary@", "addKit",
                                    "--id", kitName,
                                    "--name", "Qt %{Qt:Version} for UWP 32bit (MSVC 2017)",
                                    "--Ctoolchain", "x86-windows-msvc2017-pe-32bit",
                                    "--Cxxtoolchain", "x86-windows-msvc2017-pe-32bit",
                                    "--qt", component.name,
                                    "--debuggerengine", "4",
                                    "--devicetype", "WinRt.Device.Local",
                                    "UNDOEXECUTE",
                                    "@SDKToolBinary@", "rmKit", "--id", kitName]);

            // patch/register docs and examples
            var installationPath = installer.value("TargetDir") + "%TARGET_INSTALL_DIR%";
            print("Register documentation and examples for: " + installationPath);
            patchQtExamplesAndDoc(component, installationPath, "Qt-5.9");

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

