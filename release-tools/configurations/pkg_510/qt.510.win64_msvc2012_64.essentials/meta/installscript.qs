/****************************************************************************
**
** Copyright (C) 2013 Digia Plc and/or its subsidiary(-ies).
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
    // if 32bit windows hide the 64bit packages
    if ( installer.environmentVariable("ProgramFiles(x86)") == "" ) {
        installer.componentByName("qt.510.win64_msvc2012_64").setValue("Virtual", "true")
        installer.componentByName("qt.510.win64_msvc2012_64").setValue("Default", "false")
        installer.componentByName("qt.510.win64_msvc2012_64.essentials").setValue("Virtual", "true")
        installer.componentByName("qt.510.win64_msvc2012_64.essentials").setValue("Default", "false")
        installer.componentByName("qt.510.win64_msvc2012_64.addons").setValue("Virtual", "true")
        installer.componentByName("qt.510.win64_msvc2012_64.addons").setValue("Default", "false")
    } else {
        // all ok
    }
}

Component.prototype.isDefault = function()
{
    if (installer.environmentVariable("VS110COMNTOOLS")) {
        return true;
    }
    return false;
}

function createShortcuts()
{
    var qtStringVersion = "5.1.0";
    // Create a batch file with the development environment
    var component_root_path = installer.value("TargetDir") + "%TARGET_INSTALL_DIR%";
    component_root_path = component_root_path.replace(/\//g, "\\");

    var batchFileName = component_root_path + "\\" + "bin" + "\\" + "qtenv2.bat";
    var contentString = "echo off\r\n";
    contentString += "echo Setting up environment for Qt usage...\r\n";
    contentString += "set PATH="  + component_root_path + "\\bin;%PATH%\r\n";
    contentString += "cd /D " + component_root_path + "\r\n";

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
                            "@StartMenuDir@/5.1.0/MSVC 2012 (64-bit)/Qt " + qtStringVersion + " 64-bit for Desktop (MSVC 2012).lnk",
                            "/A /Q /K " + batchFileName);
    // Assistant
    component.addOperation( "CreateShortcut",
                            component_root_path + "/bin/assistant.exe",
                            "@StartMenuDir@/5.1.0/MSVC 2012 (64-bit)/Assistant.lnk");

    // Designer
    component.addOperation( "CreateShortcut",
                            component_root_path + "/bin/designer.exe",
                            "@StartMenuDir@/5.1.0/MSVC 2012 (64-bit)/Designer.lnk");

    // Linguist
    component.addOperation( "CreateShortcut",
                            component_root_path + "/bin/linguist.exe",
                            "@StartMenuDir@/5.1.0/MSVC 2012 (64-bit)/Linguist.lnk");
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
            // Create a batch file and shortcuts with the development environment
            createShortcuts();

            if (installer.value("SDKToolBinary") == "")
                return;
            var qmakeBinary = "@TargetDir@/%TARGET_INSTALL_DIR%/bin/qmake.exe";

            component.addOperation("Execute",
                new Array("{0}", "@SDKToolBinary@", "addQt", "--id", component.name, "--name", "Qt 5.1.0 MSVC2012 64bit", "--type", "Qt4ProjectManager.QtVersion.Desktop", "--qmake", qmakeBinary));

            component.addOperation("Execute",
                new Array("{0}", "@SDKToolBinary@", "addKit", "--id", component.name + "_kit", "--name", "Desktop Qt 5.1.0 MSVC2012 64bit", "--toolchain", "x86-windows-msvc2012-pe-64bit", "--qt", component.name, "--debuggerengine", "4", "--devicetype", "Desktop"));

        } catch( e ) {
            print( e );
        }
    }
}
