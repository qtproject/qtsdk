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

    var platform = "";
    var qmakeBinary = "@TargetDir@" + "%TARGET_INSTALL_DIR%/bin/qmake";
    var sdpDirectoryPath = installer.value("QNX660_SDP_PATH");
    var sdpQnxToolsExtension = "";

    if (installer.value("os") == "x11") {
        platform = "linux";
    }
    if (installer.value("os") == "win") {
        platform = "windows";
        sdpQnxToolsExtension = ".exe";
    }

    var qtPath = "@TargetDir@" + "%TARGET_INSTALL_DIR%";
    addInitQtPatchOperation(component, platform, qtPath, Dir.toNativeSparator(qmakeBinary + sdpQnxToolsExtension), "emb-arm-qt5");

    if (installer.value("SDKToolBinary") == "")
        return;

    // add Qt to QtCreator
    component.addOperation("Execute",
                           ["@SDKToolBinary@", "addQt",
                            "--id", component.name,
                            "--name", "Qt %{Qt:Version} for QNX 6.6.0 x86",
                            "--type", "Qt4ProjectManager.QtVersion.QNX.QNX",
                            "--qmake", Dir.toNativeSparator(qmakeBinary + sdpQnxToolsExtension),
                            "SDKPath", "QString:" + Dir.toNativeSparator(sdpDirectoryPath),
                            "UNDOEXECUTE",
                            "@SDKToolBinary@", "rmQt", "--id", component.name]);

    // add Kit to QtCreator
    component.addOperation("Execute",
                           ["@SDKToolBinary@", "addKit",
                            "--id", component.name + ".kit",
                            "--name", "Qt %{Qt:Version} for QNX 6.6.0 x86",
                            "--debuggerid", "opt_qnx660_debugger_x86",
                            "--devicetype", "QnxOsType",
                            "--sysroot", Dir.toNativeSparator(sdpDirectoryPath + "/target/qnx6"),
                            "--toolchain", "Qnx.QccToolChain:opt_qnx660_qcc_x86",
                            "--qt", component.name,
                            "--mkspec", "qnx-x86-qcc",
                            "UNDOEXECUTE",
                            "@SDKToolBinary@", "rmKit", "--id", component.name + ".kit"]);

    // patch/register docs and examples
    var installationPath = installer.value("TargetDir") + "%TARGET_INSTALL_DIR%";
    print("Register documentation and examples for: " + installationPath);
    patchQtExamplesAndDoc(component, installationPath, "Qt-5.4");
}

