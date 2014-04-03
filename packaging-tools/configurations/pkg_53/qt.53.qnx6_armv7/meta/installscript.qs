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

// constructor
function Component()
{
    // add dynamic dependency for mingw482 TC for QNX packages on Windows
    if (installer.value("os") == "win") {
        var mingw_tc_component = "qt.tools.win32_mingw482";
        component.addDependency(mingw_tc_component);
    }
}

Component.prototype.beginInstallation = function()
{
    installer.setValue(component.name + "_qtpath", "@TargetDir@" + "%TARGET_INSTALL_DIR%");
}

Component.prototype.createOperations = function()
{
    component.createOperations();

    var qtStringVersion = "5.3.0";
    var qmakeBinary = "";
    var platform = "";
    var sdpDirectoryPath = "@HomeDir@" + "/qnx660";
    var widget = gui.pageWidgetByObjectName("DynamicSetPathForSDPForm");

    if (widget != null)
        if (widget.SDPdirectory.text != "")
            sdpDirectoryPath = widget.SDPdirectory.text;

    if (installer.value("os") == "x11") {
        qmakeBinary = "@TargetDir@" + "%TARGET_INSTALL_DIR%/bin/qmake";
        platform = "linux";
        sdpDirectoryPath.replace(/\/$/, "");
    }
    if (installer.value("os") == "win") {
        qmakeBinary = "@TargetDir@" + "%TARGET_INSTALL_DIR%/bin/qmake.exe";
        platform = "windows";
        sdpDirectoryPath.replace(/\\$/, "");
    }

    var qtPath = "@TargetDir@" + "%TARGET_INSTALL_DIR%";
    addInitQtPatchOperation(component, platform, qtPath, qmakeBinary, "emb-arm-qt5");

    if (installer.value("SDKToolBinary") == "")
        return;

    // add QCC (QNX SDP) to QtCreator
    component.addOperation("Execute",
                           ["@SDKToolBinary@", "addTC",
                            "--id", "Qnx.QccToolChain:opt_qnx660_qcc_device",
                            "--name", "QCC for QNX 6.6.0 Device",
                            "--path", sdpDirectoryPath + "/host/linux/x86/usr/bin/qcc",
                            "--abi", "arm-linux-generic-elf-32bit",
                            "--supportedAbis", "arm-linux-generic-elf-32bit,x86-linux-generic-elf-32bit",
                            "Qnx.QnxToolChain.NDKPath", "QString:" + sdpDirectoryPath,
                            "UNDOEXECUTE",
                            "@SDKToolBinary@", "rmTC", "--id", "Qnx.QccToolChain:opt_qnx660_qcc_device"]);

    // add QCC Debugger (QNX SDP) to QtCreator
    component.addOperation("Execute",
                           ["@SDKToolBinary@", "addDebugger",
                            "--id", "opt_qnx660_debugger_device",
                            "--name", "Debugger for QNX 6.6.0 Device",
                            "--engine", "1",
                            "--binary", sdpDirectoryPath + "/host/linux/x86/usr/bin/ntoarmv7-gdb",
                            "--abis", "arm-linux-generic-elf-32bit",
                            "UNDOEXECUTE",
                            "@SDKToolBinary@", "rmDebugger", "--id", "opt_qnx660_debugger_device"]);

    // add Qt to QtCreator
    component.addOperation("Execute",
                           ["@SDKToolBinary@", "addQt",
                            "--id", component.name,
                            "--name", "Qt " + qtStringVersion + " for QNX 6.6.0 Device",
                            "--type", "Qt4ProjectManager.QtVersion.QNX.QNX",
                            "--qmake", qmakeBinary,
                            "SDKPath", "QString:" + sdpDirectoryPath,
                            "UNDOEXECUTE",
                            "@SDKToolBinary@", "rmQt", "--id", component.name]);

    // add Kit to QtCreator
    component.addOperation("Execute",
                           ["@SDKToolBinary@", "addKit",
                            "--id", component.name + ".kit",
                            "--name", "Qt " + qtStringVersion + " for QNX 6.6.0 Device",
                            "--debuggerid", "opt_qnx660_debugger_device",
                            "--devicetype", "QnxOsType",
                            "--sysroot", sdpDirectoryPath + "/target/qnx6",
                            "--toolchain", "Qnx.QccToolChain:opt_qnx660_qcc_device",
                            "--qt", component.name,
                            "--mkspec", "qnx-armv7le-qcc",
                            "UNDOEXECUTE",
                            "@SDKToolBinary@", "rmKit", "--id", component.name + ".kit"]);

    // patch/register docs and examples
    var installationPath = installer.value("TargetDir") + "%TARGET_INSTALL_DIR%";
    print("Register documentation and examples for: " + installationPath);
    patchQtExamplesAndDoc(component, installationPath, "Qt-5.3");
}

