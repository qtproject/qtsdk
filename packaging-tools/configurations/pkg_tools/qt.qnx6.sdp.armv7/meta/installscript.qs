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

Component.prototype.createOperations = function()
{
    component.createOperations();

    var sdpDirectoryPath = installer.value("QNX660_SDP_PATH");
    var sdpQnxHostPath = "";
    var sdpQnxToolsExtension = "";

    if (installer.value("os") == "x11") {
        sdpQnxHostPath = sdpDirectoryPath + "/host/linux/x86";
    }
    if (installer.value("os") == "win") {
        sdpQnxHostPath = sdpDirectoryPath + "/host/win32/x86";
        sdpQnxToolsExtension = ".exe";
    }

    // add QCC (QNX SDP) to QtCreator
    component.addOperation("Execute",
                           ["@SDKToolBinary@", "addTC",
                            "--id", "Qnx.QccToolChain:opt_qnx660_qcc_armv7",
                            "--name", "QCC for QNX 6.6.0 armv7",
                            "--path", Dir.toNativeSparator(sdpQnxHostPath + "/usr/bin/qcc" + sdpQnxToolsExtension),
                            "--abi", "arm-linux-generic-elf-32bit",
                            "--supportedAbis", "arm-linux-generic-elf-32bit,x86-linux-generic-elf-32bit",
                            "Qnx.QnxToolChain.NDKPath", "QString:" + Dir.toNativeSparator(sdpDirectoryPath),
                            "UNDOEXECUTE",
                            "@SDKToolBinary@", "rmTC", "--id", "Qnx.QccToolChain:opt_qnx660_qcc_armv7"]);

    // add QCC Debugger (QNX SDP) to QtCreator
    component.addOperation("Execute",
                           ["@SDKToolBinary@", "addDebugger",
                            "--id", "opt_qnx660_debugger_armv7",
                            "--name", "Debugger for QNX 6.6.0 armv7",
                            "--engine", "1",
                            "--binary", Dir.toNativeSparator(sdpQnxHostPath + "/usr/bin/ntoarmv7-gdb" + sdpQnxToolsExtension),
                            "--abis", "arm-linux-generic-elf-32bit",
                            "UNDOEXECUTE",
                            "@SDKToolBinary@", "rmDebugger", "--id", "opt_qnx660_debugger_armv7"]);
}
