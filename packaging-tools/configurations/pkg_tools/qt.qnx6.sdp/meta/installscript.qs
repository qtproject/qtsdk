/*****************************************************************************
**
** Copyright (C) 2014 Digia Plc and/or its subsidiary(-ies).
** Copyright (C) 2014 BlackBerry Limited. All rights reserved.
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

var Dir = new function () {
    this.toNativeSparator = function (path) {
        if (installer.value("os") == "win")
            return path.replace(/\//g, '\\');
        return path;
    }
};

validateSDPDirectory = function(path)
{
    if (path != "") {
        if (installer.fileExists(path + installer.value("QNX660_ENV_FILE")))
            return true;
    }
    return false;
}

// constructor
function Component()
{
    // Add a user interface file called SetPathForSDPForm
    gui.pageWidgetByObjectName("ComponentSelectionPage").completeChanged.connect(Component.prototype.initPage);

    var SDPdirectory;
    // use the right env file and default sdp path on x11 and win
    if (installer.value("os") == "x11") {
        SDPdirectory = Dir.toNativeSparator("/opt/qnx660");
        installer.setValue("QNX660_ENV_FILE", "/qnx660-env.sh");
    } else if (installer.value("os") == "win") {
        SDPdirectory = Dir.toNativeSparator("c:/qnx660");
        installer.setValue("QNX660_ENV_FILE", "/qnx660-env.bat");
    }

    if ( !installer.containsValue("QNX660_SDP_PATH") ) {
        installer.setValue("QNX660_SDP_PATH", SDPdirectory );
    }
}

Component.prototype.initPage = function()
{
    installer.calculateComponentsToInstall();

    if (component.installationRequested()) {
        if (installer.addWizardPage( component, "SetPathForSDPForm", QInstaller.ReadyForInstallation )) {
            var widget = gui.pageWidgetByObjectName("DynamicSetPathForSDPForm");
            if (widget != null) {
                widget.SDPchooser.clicked.connect(this, Component.prototype.dirRequested);
                widget.SDPdirectory.textChanged.connect(this, Component.prototype.textChanged);

                // set the initial by default directory
                widget.SDPdirectory.text = installer.value("QNX660_SDP_PATH");

                // validate whether the initial by default directory is good enough
                widget.complete = validateSDPDirectory(widget.SDPdirectory.text);
            }
        }
    } else {
        installer.removeWizardPage(component, "SetPathForSDPForm");
    }
}

Component.prototype.dirRequested = function () {
    var widget = gui.pageWidgetByObjectName("DynamicSetPathForSDPForm");
    if (widget != null) {
        var newDirName = QFileDialog.getExistingDirectory("Choose your SDP directory.", widget.SDPdirectory.text);
        widget.SDPdirectory.text = Dir.toNativeSparator(newDirName);
    }
}

Component.prototype.textChanged = function(text) {
    var widget = gui.pageWidgetByObjectName("DynamicSetPathForSDPForm");
    if (widget != null) {
        if (text != "")
            if (validateSDPDirectory(text)) {
                widget.complete = true;
                installer.setValue("QNX660_SDP_PATH", text);
                return;
            }
        widget.complete = false;
    }
}
