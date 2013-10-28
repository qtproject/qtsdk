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
    if (installer.value("os") == "mac") {
        var otoolCheck = installer.execute("/usr/bin/which", new Array("otool"))[0];
        if (!otoolCheck) {
            QMessageBox["warning"]("otoolCheckError",
                                   qsTr("No otool found!"),
                                   qsTr("You need the Xcode command line tools installed.\n" +
                                   "Download the Xcode command line tools from https://developer.apple.com/downloads\n"));
        }
    }

    gui.pageWidgetByObjectName("LicenseAgreementPage").entered.connect(changeLicenseLabels);
}

changeLicenseLabels = function()
{
    page = gui.pageWidgetByObjectName("LicenseAgreementPage");
    page.AcceptLicenseLabel.setText("I h<u>a</u>ve read and agree to the following terms contained in the license agreements accompanying the Qt installer and additional items. I agree that my use of the Qt installer is governed by the terms and conditions contained in these license agreements.");
    page.RejectLicenseLabel.setText("I <u>d</u>o not accept the terms and conditions of the above listed license agreements. Please note by checking the box, you must cancel the installation or downloading the Qt and must destroy all copies, or portions thereof, of the Qt in your possessions.");
}

qmakeOutputInstallerKey = function(aComponent)
{
    var qmakeOutputInstallerKey = aComponent.name;
    // try to find the parent
    if (qmakeOutputInstallerKey.lastIndexOf(".") !== -1) {
        qmakeOutputInstallerKey = qmakeOutputInstallerKey.slice(0, qmakeOutputInstallerKey.lastIndexOf("."));
    }
    qmakeOutputInstallerKey += "_qmakeoutput";
    return qmakeOutputInstallerKey;
}

addInitQtPatchOperation = function(aComponent, aOS, aQtPath, aQmakePath, version)
{
    aComponent.addOperation("ConsumeOutput", qmakeOutputInstallerKey(aComponent), aQmakePath, "-query");
    aComponent.addOperation("QtPatch", aOS, aQtPath, version);
}

Component.prototype.createOperations = function()
{
    component.createOperations();

    if (installer.value("os") == "win") {
        try {
            var win_application = installer.value("TargetDir") + "/MaintenanceTool.exe";

            component.addOperation( "CreateShortcut",
                                    win_application,
                                    "@StartMenuDir@/Uninstall Qt.lnk",
                                    " --uninstall");
        } catch( e ) {
            print( e );
        }
    }
}
