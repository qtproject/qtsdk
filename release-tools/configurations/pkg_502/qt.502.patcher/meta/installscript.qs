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



function Component()
{
    if (installer.isInstaller()) {
        installer.aboutCalculateComponentsToInstall.connect( this, addDynamicDependencies );
    }
}

addDynamicDependencies = function(page)
{
    if (page <= QInstaller.ComponentSelection)
        return;
    component.setValue("Dependencies", "");
    var dynamicDependencies = new Array();
    dynamicDependencies.push("qt.502.gcc_64.essentials");
    dynamicDependencies.push("qt.502.gcc_64.addons");
    dynamicDependencies.push("qt.502.gcc.essentials");
    dynamicDependencies.push("qt.502.gcc.addons");
    dynamicDependencies.push("qt.502.clang_64.essentials");
    dynamicDependencies.push("qt.502.clang_64.addons");
    dynamicDependencies.push("qt.502.win32_mingw47.addons");
    dynamicDependencies.push("qt.502.win32_mingw47.essentials");
    dynamicDependencies.push("qt.502.win32_msvc2010.essentials");
    dynamicDependencies.push("qt.502.win32_msvc2010.addons");
    dynamicDependencies.push("qt.502.win32_msvc2010_opengl.essentials");
    dynamicDependencies.push("qt.502.win32_msvc2010_opengl.addons");
    dynamicDependencies.push("qt.502.win64_msvc2010_64.essentials");
    dynamicDependencies.push("qt.502.win64_msvc2010_64.addons");
    dynamicDependencies.push("qt.502.win64_msvc2012_64.essentials");
    dynamicDependencies.push("qt.502.win64_msvc2012_64.addons");

    for (var i = 0; i < dynamicDependencies.length; i++) {
        componentName = dynamicDependencies[i];
        if (installer.componentByName(componentName) &&
            installer.componentByName(componentName).installationRequested()) {
            component.addDependency(componentName);
            print(componentName + " added");
        }
    }
}
/**
TODO: separate patcher needed for each qt version if online repositories are to be used
*/
Component.prototype.createOperations = function()
{
    component.createOperations();

    if (installer.value("os") == "x11") {
        try {
            // patch Qt binaries
            if (installer.value("qt.502.gcc_64.essentials_qtpath"))
                component.addOperation("QtPatch", "linux", installer.value("qt.502.gcc_64.essentials_qtpath"), "qt5");
            if (installer.value("qt.502.gcc.essentials_qtpath"))
                component.addOperation("QtPatch", "linux", installer.value("qt.502.gcc.essentials_qtpath"), "qt5");
        } catch( e ) {
            print( e );
        }
    }

    if (installer.value("os") == "win") {
        try {
            // patch Qt binaries
            if (installer.value("qt.502.win32_mingw47.essentials_qtpath"))
                component.addOperation("QtPatch", "windows", installer.value("qt.502.win32_mingw47.essentials_qtpath"), "qt5");
            if (installer.value("qt.502.win32_msvc2010.essentials_qtpath"))
                component.addOperation("QtPatch", "windows", installer.value("qt.502.win32_msvc2010.essentials_qtpath"), "qt5");
            if (installer.value("qt.502.win32_msvc2010_opengl.essentials_qtpath"))
                component.addOperation("QtPatch", "windows", installer.value("qt.502.win32_msvc2010_opengl.essentials_qtpath"), "qt5");
            if (installer.value("qt.502.win64_msvc2010_64.essentials_qtpath"))
                component.addOperation("QtPatch", "windows", installer.value("qt.502.win64_msvc2010_64.essentials_qtpath"), "qt5");
            if (installer.value("qt.502.win64_msvc2012_64.essentials_qtpath"))
                component.addOperation("QtPatch", "windows", installer.value("qt.502.win64_msvc2012_64.essentials_qtpath"), "qt5");
        } catch( e ) {
            print( e );
        }
    }

    if (installer.value("os") == "mac") {
        try {
            // patch Qt binaries
            component.addOperation("QtPatch", "mac", installer.value("qt.502.clang_64.essentials_qtpath"), "qt5");
        } catch( e ) {
            print( e );
        }
    }
}

