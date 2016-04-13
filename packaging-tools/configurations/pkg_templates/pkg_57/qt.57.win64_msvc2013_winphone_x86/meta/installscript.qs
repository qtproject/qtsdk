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
            addInitQtPatchOperation(component, "windows", qtPath, qmakeBinary, "qt5");

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
            patchQtExamplesAndDoc(component, installationPath, "Qt-5.7");

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

