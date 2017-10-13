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

var native_path_separator = "/";

// constructor
function Component()
{
    installer.valueChanged.connect(this, Component.prototype.reactOnTargetDirChange);

    if (installer.value("os") == "win") {
        // Creator needs vcredist 32bit on windows
        component.addDependency("qt.tools.vcredist_msvc%QTC_MSVC%_x86");
        if (systemInfo.currentCpuArchitecture == "x86_64")
            component.addDependency("qt.tools.vcredist_msvc%QTC_MSVC%_x64");
    }

    // set the default values to settings file and binary path
    Component.prototype.reactOnTargetDirChange("TargetDir", installer.value("TargetDir"));
}

Component.prototype.beginInstallation = function()
{
    if (installer.value("os") === "win")
        component.addStopProcessForUpdateRequest(component.qtCreatorBinaryPath);
}

Component.prototype.reactOnTargetDirChange = function(key, value)
{
    if (key == "TargetDir") {
        component.qtCreatorBinaryPath = value;
        if (installer.value("os") == "win") {
            component.qtCreatorSettingsFile = value + "/%TARGET_INSTALL_DIR%/share/qtcreator/QtProject/QtCreator.ini";
            component.qtCreatorBinaryPath = value + "\\%TARGET_INSTALL_DIR%\\bin\\qtcreator.exe";
            component.qtCreatorBinaryPath = component.qtCreatorBinaryPath.replace(/\//g, "\\");
        } else if (installer.value("os") == "mac") {
            component.qtCreatorSettingsFile = value + "/%TARGET_INSTALL_DIR%/Contents/Resources/QtProject/QtCreator.ini";
            component.qtCreatorBinaryPath = value + "/%TARGET_INSTALL_DIR%/Contents/MacOS/Qt Creator";
            // fix duplicate forward slashes in path
            component.qtCreatorBinaryPath = component.qtCreatorBinaryPath.replace(/\/+/g, "/");
        } else {
            component.qtCreatorSettingsFile = value + "/%TARGET_INSTALL_DIR%/share/qtcreator/QtProject/QtCreator.ini";
            component.qtCreatorBinaryPath = value + "/%TARGET_INSTALL_DIR%/bin/qtcreator";
            // fix duplicate forward slashes in path
            component.qtCreatorBinaryPath = component.qtCreatorBinaryPath.replace(/\/+/g, "/");
        }
    }
}

Component.prototype.createOperations = function()
{
    // Call the base createOperations and afterwards set some registry settings
    component.createOperations();
    var maintenanceToolPath;

    if (installer.value("os") == "win") {
        component.addOperation("CreateShortcut",
                               component.qtCreatorBinaryPath,
                               "@StartMenuDir@\\Qt Creator %QTC_DISPLAY_VERSION% (Community).lnk",
                               "workingDirectory=@homeDir@");
    }
    if (installer.value("os") == "x11") {
        component.addOperation("InstallIcons", installer.value("TargetDir") + "%TARGET_INSTALL_DIR%/share/icons" );
        component.addOperation("CreateDesktopEntry",
                               "TheQtCompany-qtcreator-%QTC_DISPLAY_VERSION%-community.desktop",
                               "Type=Application\nExec=\"" + component.qtCreatorBinaryPath + "\"\nName=Qt Creator %QTC_DISPLAY_VERSION% (Community)\nGenericName=The IDE of choice for Qt development.\nIcon=QtProject-qtcreator\nStartupWMClass=qtcreator\nTerminal=false\nCategories=Development;IDE;Qt;\nMimeType=text/x-c++src;text/x-c++hdr;text/x-xsrc;application/x-designer;application/vnd.qt.qmakeprofile;application/vnd.qt.xml.resource;text/x-qml;text/x-qt.qml;text/x-qt.qbs;");
    }

    // use shared install settings
    settingsPathFromFile = function(filePath) {
        var postfix = "QtProject/QtCreator.ini";
        if (filePath.endsWith(postfix))
           return filePath.substr(0, filePath.length - postfix.length);
        return "";
    };
    var sharedInstallSettings = settingsPathFromFile(installer.value("QtCreatorInstallerSettingsFile"));
    if (sharedInstallSettings != "") {
        component.addOperation("Settings",
                               "path=" + component.qtCreatorSettingsFile,
                               "method=set",
                               "key=Settings/InstallSettings",
                               "value=" + sharedInstallSettings);
    }
}
