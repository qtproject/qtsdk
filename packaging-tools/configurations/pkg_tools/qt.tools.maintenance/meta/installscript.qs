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
    if (installer.value("os") == "win") {
        component.installerbaseBinaryPath = "@TargetDir@/temp/SDKMaintenanceToolBase.exe";
    }
    else if (installer.value("os") == "x11" || installer.value("os") == "mac")
    {
        component.installerbaseBinaryPath = "@TargetDir@/.tempSDKMaintenanceTool";
    }
    installer.setInstallerBaseBinary(component.installerbaseBinaryPath);
}


Component.prototype.createOperationsForArchive = function(archive)
{
    //installer.performOperation in older versions of the installer framework don't supports @TargetDir@
    var normalizedInstallerbaseBinaryPath = component.installerbaseBinaryPath.replace(/@TargetDir@/,
        installer.value("TargetDir"));

    installer.performOperation("SimpleMoveFile",
        new Array(normalizedInstallerbaseBinaryPath, normalizedInstallerbaseBinaryPath + "_backup"));
    component.createOperationsForArchive(archive);
}

Component.prototype.createOperations = function()
{
    // Call the base createOperations and afterwards set some registry settings (unpacking ...)
    component.createOperations();
    var maintenance_tool_bin = installer.value("TargetDir") + "/MaintenanceTool";

    if ( installer.value("os") == "win" )
    {
        var win_maintenance_tool_bin = maintenance_tool_bin + ".exe"
        component.addOperation( "SetQtCreatorValue",
                                "",
                                "Updater",
                                "Application",
                                win_maintenance_tool_bin );
        // create shortcut
        component.addOperation( "CreateShortcut",
                                win_maintenance_tool_bin,
                                "@StartMenuDir@/Qt Maintenance Tool.lnk",
                                "workingDirectory=@TargetDir@" );
    }
    if ( installer.value("os") == "x11" )
    {
        component.addOperation( "SetQtCreatorValue",
                                "",
                                "Updater",
                                "Application",
                                maintenance_tool_bin );

        component.addOperation( "CreateDesktopEntry",
                                "QtOpensource-MaintenanceTool.desktop",
                                "Type=Application\nExec=@TargetDir@/MaintenanceTool\nPath=@TargetDir@\nName=Qt Maintenance Tool (Opensource)\nGenericName=Install or uninstall Qt components.\nIcon=QtIcon\nTerminal=false\nCategories=Development;Qt;"
                               );
    }
    if ( installer.value("os") == "mac" )
    {
        var mac_maintenance_tool_bin = maintenance_tool_bin + ".app/Contents/MacOS/MaintenanceTool"
        component.addOperation( "SetQtCreatorValue",
                                "",
                                "Updater",
                                "Application",
                                mac_maintenance_tool_bin );
    }

    component.addOperation( "SetQtCreatorValue",
                            "",
                            "Updater",
                            "CheckOnlyArgument",
                            "--checkupdates" );
    component.addOperation( "SetQtCreatorValue",
                            "",
                            "Updater",
                            "RunUiArgument",
                            "--updater" );

}


