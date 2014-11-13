/*****************************************************************************
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
*****************************************************************************/

// constructor
function Component()
{
    if (installer.value("os") == "mac") {
        var installNameToolCheck = installer.execute("/usr/bin/xcrun", ["-f", "install_name_tool"])[1];
        if (installNameToolCheck !== 0) {
            QMessageBox["warning"]("installNameToolCheckError",
                    qsTr("No install_name_tool found!"),
                    qsTr("You need to install Xcode (https://developer.apple.com/xcode/). If you already have Xcode installed, you need to set the active developer directory with 'xcode-select'.\n"));
        }
        var otoolCheck = installer.execute("/usr/bin/xcrun", ["-f", "otool"])[1];
        if (otoolCheck !== 0) {
            QMessageBox["warning"]("otoolCheckError",
                    qsTr("No otool found!"),
                    qsTr("You need to install Xcode (https://developer.apple.com/xcode/). If you already have Xcode installed, you need to set the active developer directory with 'xcode-select'.\n"));
        }
    }

    try {
        gui.pageWidgetByObjectName("LicenseAgreementPage").entered.connect(changeInstallerLicenseLabels);
    } catch(e) {
        // "gui" will not be defined for --checkupdates
    }
}


changeInstallerLicenseLabels = function()
{
    page = gui.pageWidgetByObjectName("LicenseAgreementPage");
    page.AcceptLicenseLabel.setText("I h<u>a</u>ve read and agree to the terms contained in the license agreements.");
    page.RejectLicenseLabel.setText("I <u>d</u>o not accept the terms and conditions of the above license agreements.");
}


qmakeOutputInstallerKey = function(aComponent)
{
    var qmakeOutputInstallerKey = aComponent.name;
    // if installing packages 5.0.2 - 5.2.x, in later releases the addons/essentials split is removed from packages
    if (qmakeOutputInstallerKey.match("essentials$") || qmakeOutputInstallerKey.match("addons$")) {
        // try to find the parent
        if (qmakeOutputInstallerKey.lastIndexOf(".") !== -1) {
            qmakeOutputInstallerKey = qmakeOutputInstallerKey.slice(0, qmakeOutputInstallerKey.lastIndexOf("."));
        }
    }
    qmakeOutputInstallerKey += "_qmakeoutput";
    return qmakeOutputInstallerKey;
}

addInitQtPatchOperation = function(aComponent, aOS, aQtPath, aQmakePath, version)
{
    aComponent.addOperation("ConsumeOutput", qmakeOutputInstallerKey(aComponent), aQmakePath, "-query");
    aComponent.addOperation("QtPatch", aOS, aQtPath, version);
}


registerQtCreatorDocumentation = function(aComponent, aPath)
{
    var settingsFile = installer.value("QtCreatorInstallerSettingsFile");
    if (settingsFile == "")
        return;

    aComponent.addOperation("Settings",
        "path=" + settingsFile,
        "method=add_array_value",
        "key=Help/InstalledDocumentation",
        "value=" + "@TargetDir@" + aPath);
}

registerQtCreatorExampleSet = function(aComponent, aDisplayName, aDocumentationPath, aExamplesPath)
{
    var settingsFile = installer.value("QtCreatorInstallerSettingsFile");
    if (settingsFile == "")
        return;

    aComponent.addOperation("Settings",
        "path=" + settingsFile,
        "method=add_array_value",
        "key=Help/InstalledExamples",
        "value=" + aDisplayName + "|" + "@TargetDir@" + aDocumentationPath + "|" + "@TargetDir@" + aExamplesPath);
}

/*****
* Global function to be used by Qt binary packages.
* This function will write qt.conf to the /bin directory. Examples and documentation paths
* will be over ridden to point into centralized doc&examples location
* @param aComponentRootPath     Full path to the Qt package (under this path the /bin should exist)
* @param aQtInstallationName    "Qt-x.x.x"
*/
patchQtExamplesAndDoc = function(aComponent, aComponentRootPath, aQtInstallationName)
{
    print("Patching doc & examples for: " + aComponentRootPath);
    var fileName = aComponentRootPath + "/" + "bin" + "/" + "qt.conf";
    print("qt.conf file: " + fileName);

    aComponent.addOperation("Settings",
        "path=" + fileName,
        "method=set",
        "key=Paths/Prefix",
        "value=..");

    aComponent.addOperation("Settings",
        "path=" + fileName,
        "method=set",
        "key=Paths/Examples",
        "value=../../Examples/" + aQtInstallationName);

    aComponent.addOperation("Settings",
        "path=" + fileName,
        "method=set",
        "key=Paths/Documentation",
        "value=../../Docs/" + aQtInstallationName);
}

patchQt4ExamplesAndDoc = function(aComponent, aComponentRootPath, aQtInstallationName)
{
    patchQtExamplesAndDoc(aComponent, aComponentRootPath, aQtInstallationName);

    print("Patching demos for: " + aComponentRootPath);
    var fileName = aComponentRootPath + "/" + "bin" + "/" + "qt.conf";
    print("qt.conf file: " + fileName);

    aComponent.addOperation("Settings",
        "path=" + fileName,
        "method=add_array_value",
        "key=Paths/Demos",
        "value=../../Examples/" + aQtInstallationName);
}


Component.prototype.createOperations = function()
{
    component.createOperations();

    if (installer.isInstaller() &&
        installer.value("os") == "win") {

        var editionName = "Qt"
        if (!(installer.value("QT_EDITION_NAME") === ""))
            editionName = installer.value("QT_EDITION_NAME");

        // shortcut to uninstaller
        component.addOperation( "CreateShortcut",
                                "@TargetDir@/MaintenanceTool.exe",
                                "@StartMenuDir@/Uninstall " + editionName + ".lnk",
                                " --uninstall");
    }
}








