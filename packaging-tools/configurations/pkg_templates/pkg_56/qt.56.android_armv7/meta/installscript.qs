/****************************************************************************
**
** Copyright (C) 2015 The Qt Company Ltd.
** Contact: http://www.qt.io/licensing/
**
** This file is part of the QtCore module of the Qt Toolkit.
**
** $QT_BEGIN_LICENSE:LGPL21$
** Commercial License Usage
** Licensees holding valid commercial Qt licenses may use this file in
** accordance with the commercial license agreement provided with the
** Software or, alternatively, in accordance with the terms contained in
** a written agreement between you and The Qt Company. For licensing terms
** and conditions see http://www.qt.io/terms-conditions. For further
** information use the contact form at http://www.qt.io/contact-us.
**
** GNU Lesser General Public License Usage
** Alternatively, this file may be used under the terms of the GNU Lesser
** General Public License version 2.1 or version 3 as published by the Free
** Software Foundation and appearing in the file LICENSE.LGPLv21 and
** LICENSE.LGPLv3 included in the packaging of this file. Please review the
** following information to ensure the GNU Lesser General Public License
** requirements will be met: https://www.gnu.org/licenses/lgpl.html and
** http://www.gnu.org/licenses/old-licenses/lgpl-2.1.html.
**
** As a special exception, The Qt Company gives you certain additional
** rights. These rights are described in The Qt Company LGPL Exception
** version 1.1, included in the file LGPL_EXCEPTION.txt in this package.
**
** $QT_END_LICENSE$
**
****************************************************************************/

// constructor
function Component()
{
    // add dynamic dependency for mingw492 TC for Android packages on Windows
    if (installer.value("os") == "win") {
        var mingw_tc_component = "qt.tools.win32_mingw492";
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

    var qmakeBinary = "";
    var platform = "";
    if (installer.value("os") == "x11") {
        qmakeBinary = "@TargetDir@" + "%TARGET_INSTALL_DIR%/bin/qmake";
        platform = "linux";
    }
    if (installer.value("os") == "mac") {
        qmakeBinary = "@TargetDir@" + "%TARGET_INSTALL_DIR%/bin/qmake";
        platform = "mac";
    }
    if (installer.value("os") == "win") {
        qmakeBinary = "@TargetDir@" + "%TARGET_INSTALL_DIR%/bin/qmake.exe";
        platform = "windows";
    }

    var qtPath = "@TargetDir@" + "%TARGET_INSTALL_DIR%";
    addInitQtPatchOperation(component, platform, qtPath, qmakeBinary, "emb-arm-qt5");

    if (installer.value("SDKToolBinary") == "")
        return;

    // add Qt into QtCreator
    component.addOperation("Execute",
                           ["@SDKToolBinary@", "addQt",
                            "--id", component.name,
                            "--name", "Qt %{Qt:Version} for Android armv7",
                            "--type", "Qt4ProjectManager.QtVersion.Android",
                            "--qmake", qmakeBinary,
                            "UNDOEXECUTE",
                            "@SDKToolBinary@", "rmQt", "--id", component.name]);

    // patch/register docs and examples
    var installationPath = installer.value("TargetDir") + "%TARGET_INSTALL_DIR%";
    print("Register documentation and examples for: " + installationPath);
    patchQtExamplesAndDoc(component, installationPath, "Qt-5.6");

    // patch qt edition
    var qconfigFile = qtPath + "/mkspecs/qconfig.pri";
    component.addOperation("LineReplace", qconfigFile, "QT_EDITION =", "QT_EDITION = OpenSource");
}

