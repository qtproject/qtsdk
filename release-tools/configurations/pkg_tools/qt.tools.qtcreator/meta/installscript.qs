/****************************************************************************
**
** Copyright (C) 2013 Digia Plc and/or its subsidiary(-ies).
** Contact: http://www.qt-project.org/legal
**
** This file is part of the tools applications of the Qt Toolkit.
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

var component_root_path = "/";
var native_path_separator = "/";

// constructor
function Component()
{
    installer.valueChanged.connect( this, Component.prototype.reactOnTargetDirChange );
    installer.installationFinished.connect( this, Component.prototype.installationFinished );
    installer.installationFinished.connect(this, Component.prototype.installationFinishedPageIsShown);

    if (installer.value("os") == "win")
    {
        // Creator needs vcredist 32bit on windows
        component.addDependency("qt.tools.vcredist")

        component.selectedChanged.connect( this, checkWhetherStopProcessIsNeeded );
        //it can't be unselected so we need to check it manually
        checkWhetherStopProcessIsNeeded();
    }

    if ( installer.value("os") == "x11" )
    {
        // set installation directory
        installer.setValue( "EmbeddedInstallationRootDir", "/usr/local/Trolltech" );
        installer.setValue( "EmbeddedToolchainDir", "/usr/local/angstrom/arm" );
    }

    // set the default values to SDKToolBinary and QtCreatorInstallerSettingsFile
    Component.prototype.reactOnTargetDirChange("TargetDir", installer.value("TargetDir"));
}

Component.prototype.reactOnTargetDirChange = function(key, value)
{
    if (key == "TargetDir") {
        if (installer.value("os") == "win") {
            installer.setValue("QtCreatorInstallerSettingsFile", value + "/%TARGET_INSTALL_DIR%/share/qtcreator/QtProject/QtCreator.ini");
            installer.setValue("SDKToolBinary", value + "\\%TARGET_INSTALL_DIR%\\bin\\sdktool.exe");
        } else if (installer.value("os") == "mac") {
            installer.setValue("QtCreatorInstallerSettingsFile", value + "/%TARGET_INSTALL_DIR%/Qt Creator.app/Contents/Resources/QtProject/QtCreator.ini");
            installer.setValue("SDKToolBinary", value + "/%TARGET_INSTALL_DIR%/Qt Creator.app/Contents/Resources/sdktool");
        } else {
            installer.setValue("QtCreatorInstallerSettingsFile", value + "/%TARGET_INSTALL_DIR%/share/qtcreator/QtProject/QtCreator.ini");
            installer.setValue("SDKToolBinary", value + "/%TARGET_INSTALL_DIR%/bin/sdktool");
        }
    }
}

buildNativeComponentRootPath = function()
{
    var target_install_dir = "%TARGET_INSTALL_DIR%";
    if (installer.value("os") == "win")
        {
        native_path_separator = "\\";
        target_install_dir = target_install_dir.replace(/\//g, "\\");
        }
    else
        {
        native_path_separator = "/";
        }

    component_root_path = installer.value("TargetDir") + target_install_dir;
}

checkWhetherStopProcessIsNeeded = function()
{
    if (installer.value("os") != "win")
        return;

    var path = component_root_path + native_path_separator + "bin" + native_path_separator;
    if (component.installationRequested() || component.uninstallationRequested())
    {
        component.setStopProcessForUpdateRequest(path + "qtcreator.exe", true);
        component.setStopProcessForUpdateRequest(path + "linguist.exe", true);
        component.setStopProcessForUpdateRequest(path + "qmlviewer.exe", true);
    }
    else
    {
        component.setStopProcessForUpdateRequest(path + "qtcreator.exe", false);
        component.setStopProcessForUpdateRequest(path + "linguist.exe", false);
        component.setStopProcessForUpdateRequest(path + "qmlviewer.exe", false);
    }
}


registerWindowsFileTypeExtensionsQt = function()
{
    var path = component_root_path + native_path_separator + "bin" + native_path_separator;
    component.addOperation( "RegisterFileType",
                            "ui",
                            path + "qtcreator.exe -client '%1'",
                            "Qt UI file",
                            "",
                            path + "qtcreator.exe,4");
    component.addOperation( "RegisterFileType",
                            "pro",
                            path + "qtcreator.exe -client '%1'",
                            "Qt Project file",
                            "",
                            path + "qtcreator.exe,5");
    component.addOperation( "RegisterFileType",
                            "pri",
                            path + "qtcreator.exe -client '%1'",
                            "Qt Project Include file",
                            "",
                            path + "qtcreator.exe,6");
    component.addOperation( "RegisterFileType",
                            "qs",
                            path + "qtcreator.exe -client '%1'",
                            "Qt Script file",
                            "",
                            path + "qtcreator.exe,0");
    component.addOperation( "RegisterFileType",
                            "qml",
                            path + "qtcreator.exe -client '%1'",
                            "Qt Quick Markup language file",
                            "",
                            path + "qtcreator.exe,0");
}


registerWindowsFileTypeExtensionsCpp = function()
{
    var headerExtensions = new Array("h", "hh", "hxx", "h++", "hpp");
    var path = component_root_path + native_path_separator + "bin" + native_path_separator;

    for (var i = 0; i < headerExtensions.length; ++i) {
        component.addOperation( "RegisterFileType",
                                headerExtensions[i],
                                path + "qtcreator.exe -client '%1'",
                                "C/C++ Header file",
                                "",
                                path + "qtcreator.exe,3");
    }

    var cppExtensions = new Array("cc", "cxx", "c++", "cp", "cpp");

    for (var i = 0; i < cppExtensions.length; ++i) {
        component.addOperation( "RegisterFileType",
                                cppExtensions[i],
                                path + "qtcreator.exe -client '%1'",
                                "C++ Source file",
                                "",
                                path + "qtcreator.exe,2");
    }

    component.addOperation( "RegisterFileType",
                            "c",
                            path + "qtcreator.exe -client '%1'",
                            "C Source file",
                            "",
                            path + "qtcreator.exe,1");

}

Component.prototype.createOperations = function()
{
    // Call the base createOperations and afterwards set some registry settings
    component.createOperations();
    buildNativeComponentRootPath();
    var path = component_root_path + native_path_separator;

    if ( installer.value("os") == "win" )
    {
        component.addOperation( "SetPluginPathOnQtCore",
                                path + "bin",
                                path + "plugins");
        component.addOperation( "SetImportsPathOnQtCore",
                                path + "bin",
                                path + "bin");
        component.addOperation( "CreateShortcut",
                                path + "bin" + native_path_separator + "qtcreator.exe",
                                "@StartMenuDir@\\Qt Creator.lnk",
                                "workingDirectory=" + path + "bin");

    }
    if ( installer.value("os") == "x11" )
    {
        component.addOperation( "SetPluginPathOnQtCore",
                                path + "lib" + native_path_separator + "qtcreator",
                                path + "lib" + native_path_separator + "qtcreator" + native_path_separator + "plugins");
        component.addOperation( "SetImportsPathOnQtCore",
                                path + "lib" + native_path_separator + "qtcreator",
                                path + "bin");
        component.addOperation( "InstallIcons", path + "share" + native_path_separator + "icons" );
        component.addOperation( "CreateDesktopEntry",
                                "qtcreator.desktop",
                                "Type=Application\nExec=" + path + "bin" + native_path_separator + "qtcreator\nPath=@homeDir@\nName=Qt Creator\nGenericName=The IDE of choice for Qt development.\nIcon=QtProject-qtcreator\nTerminal=false\nCategories=Development;IDE;Qt;\nMimeType=text/x-c++src;text/x-c++hdr;text/x-xsrc;application/x-designer;application/vnd.nokia.qt.qmakeprofile;application/vnd.nokia.xml.qt.resource;"
                                );
    }
    if (installer.value("os") == "mac")
    {
    }
}

Component.prototype.installationFinished = function()
{
    if (!component.installed)
        return;

    if (component.installed && installer.isInstaller() && installer.status == QInstaller.Success)
    {
        var path = component_root_path + native_path_separator;
        if (installer.value("os") == "win")
        {
            installer.setValue("RunProgram", "\"" + path + "bin" + native_path_separator + "qtcreator.exe\"");
        }
        else if (installer.value("os") == "x11")
        {
            installer.setValue("RunProgram", "\"" + path + "bin" + native_path_separator + "qtcreator\"");
        }
        else if (installer.value("os") == "mac")
        {
            installer.setValue("RunProgram", "\"" + installer.value("TargetDir") + "/Qt Creator.app/Contents/MacOS/Qt Creator\"");
        }
        installer.setValue("RunProgramDescription", "Launch Qt Creator");
    }

    // check if the user wants to register file types with QtCreator
    if (installer.value("os") == "win" && installer.isInstaller() && installer.status == QInstaller.Success) {
        var isQtFileAssociationCheckBoxForm = component.userInterface( "QtFileAssociationCheckBoxForm" ).readMeCheckBox.checked;
        if (isQtFileAssociationCheckBoxForm) {
            registerWindowsFileTypeExtensionsQt();
        }
        var isCppFileAssociationCheckBoxForm = component.userInterface( "CppFileAssociationCheckBoxForm" ).readMeCheckBox.checked;
        if (isCppFileAssociationCheckBoxForm) {
            registerWindowsFileTypeExtensionsCpp();
        }
    }
}

Component.prototype.installationFinishedPageIsShown = function()
{
    try {
        if (installer.isInstaller() && installer.status == QInstaller.Success) {
            installer.addWizardPageItem( component, "QtFileAssociationCheckBoxForm", QInstaller.InstallationFinished );
            installer.addWizardPageItem( component, "CppFileAssociationCheckBoxForm", QInstaller.InstallationFinished );
        }
    } catch(e) {
        print(e);
    }
}

