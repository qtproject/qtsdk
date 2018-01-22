/****************************************************************************
**
** Copyright (C) 2018 The Qt Company Ltd.
** Contact: https://www.qt.io/licensing/
**
** This file is part of Qt 3D Studio.
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
    if (installer.isOfflineOnly()) {
        component.setValue("Virtual", "false")
        component.setValue("Default", "true")
    }

    component.loaded.connect(this, Component.prototype.loaded);
    installer.installationFinished.connect(this, Component.prototype.installationFinishedPageIsShown);
    installer.finishButtonClicked.connect(this, Component.prototype.installationFinished);
    installer.valueChanged.connect(this, Component.prototype.reactOnTargetDirChange);

    if (installer.value("os") == "win") {
        if (systemInfo.currentCpuArchitecture == "x86_64")
            component.addDependency("qt.tools.vcredist_msvc2015_x64");
    }

    // set the default values to SDKToolBinary
    Component.prototype.reactOnTargetDirChange("TargetDir", installer.value("TargetDir"));
}

Component.prototype.loaded = function()
{
    try {
        if (installer.value("os") == "win" && installer.isInstaller())
            installer.addWizardPageItem(component, "AssociateCommonFiletypesForm", QInstaller.TargetDirectory);
    } catch(e) {
        print(e);
    }
}

Component.prototype.beginInstallation = function()
{
    if (installer.value("os") === "win")
        component.addStopProcessForUpdateRequest(component.qt3DStudioBinaryPath);
}

Component.prototype.reactOnTargetDirChange = function(key, value)
{
    if (key == "TargetDir") {
        if (installer.value("os") == "win") {
            component.qt3DStudioBinPath = value + "\\%TARGET_INSTALL_DIR%\\bin";
            component.qt3DStudioBinPath = component.qt3DStudioBinPath.replace(/\//g, "\\");
            component.platformPluginsPath = value + "\\%TARGET_INSTALL_DIR%\\plugins\\platforms";
            component.platformPluginsPath = component.platformPluginsPath.replace(/\//g, "\\");
            component.imageformatPluginsPath = value + "\\%TARGET_INSTALL_DIR%\\plugins\\imageformats";
            component.imageformatPluginsPath = component.imageformatPluginsPath.replace(/\//g, "\\");

            component.qt3DStudioBinaryPath = value + "\\%TARGET_INSTALL_DIR%\\bin\\Qt3DStudio.exe";
            component.qt3DStudioBinaryPath = component.qt3DStudioBinaryPath.replace(/\//g, "\\");
            component.qt3DViewerBinaryPath = value + "\\%TARGET_INSTALL_DIR%\\bin\\Qt3DViewer.exe";
            component.qt3DViewerBinaryPath = component.qt3DViewerBinaryPath.replace(/\//g, "\\");

        } else if (installer.value("os") == "mac") {
            component.qt3DStudioBinaryPath = value + "/%TARGET_INSTALL_DIR%/bin/Qt3DStudio.app/Contents/MacOS/Qt3DStudio";
            // fix duplicate forward slashes in path
            component.qt3DStudioBinaryPath = component.qt3DStudioBinaryPath.replace(/\/+/g, "/");
        } else {
            component.qt3DStudioBinPath = value + "/%TARGET_INSTALL_DIR%/bin";
            component.qt3DStudioBinPath = component.qt3DStudioBinPath.replace(/\/+/g, "/");
            component.platformPluginsPath = value + "/%TARGET_INSTALL_DIR%/plugins/platforms";
            component.platformPluginsPath = component.platformPluginsPath.replace(/\/+/g, "/");
        }
    }
}

function registerWindowsFileTypeExtensions()
{
    try {
        component.addOperation("RegisterFileType",
                                "uip",
                                "\"" + component.qt3DStudioBinaryPath + "\" \"%1\"",
                                "Studio uip File",
                                "application/uip",
                                component.qt3DStudioBinaryPath + ",0");
        component.addOperation("RegisterFileType",
                                "uia",
                                "\"" + component.qt3DViewerBinaryPath + "\" \"%1\"",
                                "Studio uia File",
                                "application/uia",
                                component.qt3DViewerBinaryPath + ",0");
    } catch (e) {
        console.log(e);
    }
}

function patchLinuxInstallation()
{
    // platforms plugin
    var platformPluginsTargetDir = component.qt3DStudioBinPath + "/platforms";
    platformPluginsTargetDir = platformPluginsTargetDir.replace(/\/+/g, "/");

    component.addOperation("Mkdir", platformPluginsTargetDir);

    var platformPluginsSourceFile = component.platformPluginsPath + "/libqxcb.so";
    platformPluginsSourceFile = platformPluginsSourceFile.replace(/\/+/g, "/");

    var platformPluginsTargetFile = platformPluginsTargetDir + "/libqxcb.so";
    platformPluginsTargetFile = platformPluginsTargetFile.replace(/\/+/g, "/");

    component.addOperation("Move", platformPluginsSourceFile, platformPluginsTargetFile);
}

function patchWindowsInstallation()
{
    // platforms plugin
    var platformPluginsTargetDir = component.qt3DStudioBinPath + "\\platforms";
    platformPluginsTargetDir = platformPluginsTargetDir.replace(/\//g, "\\");
    component.addOperation("Mkdir", platformPluginsTargetDir);

    var platformPluginsSourceFile = component.platformPluginsPath + "\\qwindows.dll";
    platformPluginsSourceFile = platformPluginsSourceFile.replace(/\//g, "\\");

    var platformPluginsTargetFile = platformPluginsTargetDir + "\\qwindows.dll";
    platformPluginsTargetFile = platformPluginsTargetFile.replace(/\//g, "\\");

    component.addOperation("Move", platformPluginsSourceFile, platformPluginsTargetFile);

    // imageformats plugin
    var imageformatPluginsTargetDir = component.qt3DStudioBinPath + "\\imageformats";
    imageformatPluginsTargetDir = imageformatPluginsTargetDir.replace(/\//g, "\\");
    component.addOperation("Mkdir", imageformatPluginsTargetDir);

    var imageformatPluginsSourceFile = component.imageformatPluginsPath + "\\qjpeg.dll";
    imageformatPluginsSourceFile = imageformatPluginsSourceFile.replace(/\//g, "\\");

    var imageformatPluginsTargetFile = imageformatPluginsTargetDir + "\\qjpeg.dll";
    imageformatPluginsTargetFile = imageformatPluginsTargetFile.replace(/\//g, "\\");

    component.addOperation("Move", imageformatPluginsSourceFile, imageformatPluginsTargetFile);

    // qml
    var path = installer.value("TargetDir") + "%TARGET_INSTALL_DIR%";
    path = path.replace(/\//g, "\\");
    var script = path + "\\copydir.cmd";
    script = script.replace(/\//g, "\\");

    var sourceDir = installer.value("TargetDir") + "%TARGET_INSTALL_DIR%" + "\\qml"
    var targetDir = installer.value("TargetDir") + "%TARGET_INSTALL_DIR%" + "\\bin\\qml"
    sourceDir = sourceDir.replace(/\//g, "\\");
    targetDir = targetDir.replace(/\//g, "\\");
    print("Qt3DStudio patching: Copying: [" + sourceDir + "] into [" + targetDir + "]")

    component.addOperation("Execute", "{0,2,3,4,5}", "c:\\Windows\\System32\\xcopy.exe", "/S", "/Y", "/Q", "/I", sourceDir, targetDir);
}

Component.prototype.createOperations = function()
{
    try {
        // call the base create operations function
        component.createOperations();
        if (installer.value("os") === "win") {
            // patch the installation
            patchWindowsInstallation()
            if (component.userInterface("AssociateCommonFiletypesForm").AssociateCommonFiletypesCheckBox.checked)
                registerWindowsFileTypeExtensions();
            component.addOperation("CreateShortcut", component.qt3DStudioBinaryPath, "@StartMenuDir@\\Qt 3D Studio.lnk",
                "workingDirectory=@TargetDir@\\bin", "iconPath=" + component.qt3DStudioBinaryPath, "iconId=0");
            component.addOperation("CreateShortcut", component.qt3DViewerBinaryPath, "@StartMenuDir@\\Qt 3D Viewer.lnk",
                "workingDirectory=@TargetDir@\\bin", "iconPath=" + component.qt3DViewerBinaryPath, "iconId=0");
            component.addOperation("CreateShortcut", "@TargetDir@/Qt3DStudioUninst.exe", "@StartMenuDir@/Uninstall Qt 3D Studio.lnk", " --uninstall");
        }
        if (installer.value("os") === "x11") {
            // patch the installation
            patchLinuxInstallation()
        }
    } catch (e) {
        console.log(e);
    }
}

Component.prototype.loaded = function ()
{
}

function isRoot()
{
    if (installer.value("os") == "x11" || installer.value("os") == "mac")
    {
        var id = installer.execute("/usr/bin/id", new Array("-u"))[0];
        id = id.replace(/(\r\n|\n|\r)/gm,"");
        if (id === "0")
        {
            return true;
        }
    }
    return false;
}

Component.prototype.installationFinishedPageIsShown = function()
{
    isroot = isRoot();
    try {
        if (component.installed && installer.isInstaller() && installer.status == QInstaller.Success && !isroot)
            installer.addWizardPageItem( component, "LaunchQt3DStudioCheckBoxForm", QInstaller.InstallationFinished );
    } catch(e) {
        print(e);
    }
}

Component.prototype.installationFinished = function()
{
    try {
        if (component.installed && installer.isInstaller() && installer.status == QInstaller.Success && !isroot) {
            var isLaunchQt3DStudioBoxChecked = component.userInterface("LaunchQt3DStudioCheckBoxForm").launchQt3DStudioCheckBox.checked;
            if (isLaunchQt3DStudioBoxChecked)
                installer.executeDetached(component.qt3DStudioBinaryPath, new Array(), "@homeDir@");
        }
    } catch(e) {
        print(e);
    }
}
