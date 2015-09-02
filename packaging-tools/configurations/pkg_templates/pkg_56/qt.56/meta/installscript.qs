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
    if ((installer.value("os") == "win")
                && !installer.isOfflineOnly()) {

        // Enable the right toolchains
        var msvc2013 = !!installer.environmentVariable("VS120COMNTOOLS");
        var msvc2015 = !!installer.environmentVariable("VS140COMNTOOLS");

        var android_armv7 = installer.componentByName("qt.56.android_armv7");
        var winphone_arm = installer.componentByName("qt.56.win64_msvc2013_winphone_arm");
        var winphone_x86 = installer.componentByName("qt.56.win64_msvc2013_winphone_x86");
        var winrt_x64 = installer.componentByName("qt.56.win64_msvc2013_winrt_x64");

        // first reset the latest Qt5.x.x package default values to false
        installer.componentByName("qt.56.win32_mingw492").setValue("Default", "false");

        installer.componentByName("qt.56.win32_msvc2013").setValue("Default", "false");
        installer.componentByName("qt.56.win64_msvc2013_64").setValue("Default", "false");
        installer.componentByName("qt.56.win32_msvc2015").setValue("Default", "false");
        installer.componentByName("qt.56.win64_msvc2015_64").setValue("Default", "false");

        if (android_armv7)
            android_armv7.setValue("Default", "false");
        if (winphone_arm)
            winphone_arm.setValue("Default", "false");
        if (winphone_x86)
            winphone_x86.setValue("Default", "false");
        if (winrt_x64)
            winrt_x64.setValue("Default", "false");

        // if 32bit windows hide the 64bit packages
        if (installer.environmentVariable("ProgramFiles(x86)") == "" ) {
            installer.componentByName("qt.56.win64_msvc2013_64").setValue("Virtual", "true");
            installer.componentByName("qt.56.win64_msvc2015_64").setValue("Virtual", "true");

            if (winphone_arm)
                winphone_arm.setValue("Virtual", "true");
            if (winphone_x86)
                winphone_x86.setValue("Virtual", "true");
            if (winrt_x64)
                winrt_x64.setValue("Virtual", "true");
        }

        // now try to determine which tool chains to select by default
        if (msvc2013) {
            // if 64bit machine
            if (!(installer.environmentVariable("ProgramFiles(x86)") == "")) {
                installer.componentByName("qt.56.win64_msvc2013_64").setValue("Default", "true");
            } else {
                installer.componentByName("qt.56.win32_msvc2013").setValue("Default", "true");
            }
        }
        if (msvc2015) {
            // if 64bit machine
            if (!(installer.environmentVariable("ProgramFiles(x86)") == "")) {
                installer.componentByName("qt.56.win64_msvc2015_64").setValue("Default", "true");
            } else {
                installer.componentByName("qt.56.win32_msvc2015").setValue("Default", "true");
            }
        }

        // if no msvc toolkits detected, choose mingw by default
        if (!msvc2013 && !msvc2015) {
            installer.componentByName("qt.56.win32_mingw492").setValue("Default", "true");
        }
    }
}


Component.prototype.createOperations = function()
{
    component.createOperations();
}

