/****************************************************************************
**
** Copyright (C) 2019 The Qt Company Ltd.
** Contact: https://www.qt.io/licensing/
**
** This file is part of the release tools of the Qt Toolkit.
**
** $QT_BEGIN_LICENSE:GPL-EXCEPT$
** Commercial License Usage
** Licensees holding valid commercial Qt licenses may use this file in
** accordance with the commercial license agreement provided with the
** Software or, alternatively, in accordance with the terms contained in
** a written agreement between you and The Qt Company. For licensing terms
** and conditions see https://www.qt.io/terms-conditions. For further
** information use the contact form at https://www.qt.io/contact-us.
**
** GNU General Public License Usage
** Alternatively, this file may be used under the terms of the GNU
** General Public License version 3 as published by the Free Software
** Foundation with exceptions as appearing in the file LICENSE.GPL3-EXCEPT
** included in the packaging of this file. Please review the following
** information to ensure the GNU General Public License requirements will
** be met: https://www.gnu.org/licenses/gpl-3.0.html.
**
** $QT_END_LICENSE$
**
****************************************************************************/

checkDebuggerVersion = function(key, expected)
{
    var debuggerVersion = installer.value(key).split('.');
    for (var i = 0; i < expected.length; ++i) {
        if (debuggerVersion.length == i)
            return true;
        if (parseInt(debuggerVersion[i]) < expected[i])
            return true;
        if (parseInt(debuggerVersion[i]) > expected[i])
            return false;
    }
    return false;
}

checkx64DebuggerVersion = function()
{
    return checkDebuggerVersion("HKEY_LOCAL_MACHINE\\SOFTWARE\\Classes\\Installer\\Dependencies\\Microsoft.Windows.X64DebuggersAndTools.x64.10\\Version", [10, 1, 17763, 132])
}

checkx86DebuggerVersion = function()
{
    return checkDebuggerVersion("HKEY_LOCAL_MACHINE\\SOFTWARE\\Classes\\Installer\\Dependencies\\Microsoft.Windows.x86DebuggersAndTools.x86.10\\Version", [10, 1, 17763, 132])
}

// constructor
function Component()
{
    if (checkx64DebuggerVersion() || checkx86DebuggerVersion())
        component.setValue("RequiresAdminRights", "true");
}

Component.prototype.createOperations = function()
{
    // Call the base createOperations and afterwards set some registry settings
    // so that the simulator finds its fonts and applications find the simulator
    component.createOperations();

    if (checkx64DebuggerVersion())
        component.addElevatedOperation("Execute", "{0,3010,1638,1618,5100}", "msiexec", "/i", "@TargetDir@\\vcredist\\X64 Debuggers And Tools-x64_en-us.msi", "/norestart", "/q");
    if (checkx86DebuggerVersion())
        component.addElevatedOperation("Execute", "{0,3010,1638,1618,5100}", "msiexec", "/i", "@TargetDir@\\vcredist\\x86 Debuggers And Tools-x86_en-us.msi", "/norestart", "/q");
}
