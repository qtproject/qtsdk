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
    if ((installer.value("os") == "win")
                && !installer.isOfflineOnly()) {

        // Enable the right toolchains
        var msvc2010 = !!installer.environmentVariable("VS100COMNTOOLS");
        var msvc2012 = !!installer.environmentVariable("VS110COMNTOOLS");

        // first reset the latest Qt5.x.x package default values to false
        installer.componentByName("qt.521.win32_mingw48").setValue("Default", "false");
        installer.componentByName("qt.521.win32_mingw48.essentials").setValue("Default", "false");
        installer.componentByName("qt.521.win32_mingw48.addons").setValue("Default", "false");

        installer.componentByName("qt.521.win32_msvc2010").setValue("Default", "false")
        installer.componentByName("qt.521.win32_msvc2010.essentials").setValue("Default", "false");
        installer.componentByName("qt.521.win32_msvc2010.addons").setValue("Default", "false");

        installer.componentByName("qt.521.win32_msvc2010_opengl").setValue("Default", "false")
        installer.componentByName("qt.521.win32_msvc2010_opengl.essentials").setValue("Default", "false");
        installer.componentByName("qt.521.win32_msvc2010_opengl.addons").setValue("Default", "false");

        installer.componentByName("qt.521.win32_msvc2012").setValue("Default", "false")
        installer.componentByName("qt.521.win32_msvc2012.essentials").setValue("Default", "false");
        installer.componentByName("qt.521.win32_msvc2012.addons").setValue("Default", "false");

        installer.componentByName("qt.521.win64_msvc2012_64").setValue("Default", "false")
        installer.componentByName("qt.521.win64_msvc2012_64.essentials").setValue("Default", "false");
        installer.componentByName("qt.521.win64_msvc2012_64.addons").setValue("Default", "false");

        installer.componentByName("qt.521.win64_msvc2012_64_opengl").setValue("Default", "false")
        installer.componentByName("qt.521.win64_msvc2012_64_opengl.essentials").setValue("Default", "false");
        installer.componentByName("qt.521.win64_msvc2012_64_opengl.addons").setValue("Default", "false");

        // if 32bit windows hide the 64bit packages
        if (installer.environmentVariable("ProgramFiles(x86)") == "" ) {
            installer.componentByName("qt.521.win64_msvc2012_64").setValue("Virtual", "true");
            installer.componentByName("qt.521.win64_msvc2012_64.essentials").setValue("Virtual", "true");
            installer.componentByName("qt.521.win64_msvc2012_64.addons").setValue("Virtual", "true");

            installer.componentByName("qt.521.win64_msvc2012_64_opengl").setValue("Virtual", "true");
            installer.componentByName("qt.521.win64_msvc2012_64_opengl.essentials").setValue("Virtual", "true");
            installer.componentByName("qt.521.win64_msvc2012_64_opengl.addons").setValue("Virtual", "true");
        }

        // now try to determine which tool chains to select by default
        if (msvc2010) {
            installer.componentByName("qt.521.win32_msvc2010.essentials").setValue("Default", "true");
            installer.componentByName("qt.521.win32_msvc2010.addons").setValue("Default", "true");
        }

        if (msvc2012) {
            installer.componentByName("qt.521.win32_msvc2012.essentials").setValue("Default", "true");
            installer.componentByName("qt.521.win32_msvc2012.addons").setValue("Default", "true");
        }

        if (!msvc2010 && !msvc2012) {
            installer.componentByName("qt.521.win32_mingw48.essentials").setValue("Default", "true");
            installer.componentByName("qt.521.win32_mingw48.addons").setValue("Default", "true");
        }
    }
}


Component.prototype.createOperations = function()
{
    component.createOperations();
}
