/****************************************************************************
**
** Copyright (C) 2016 The Qt Company Ltd.
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

// constructor
function Component()
{
    component.setValue("RequiresAdminRights", "true");
}

Component.prototype.createOperations = function()
{
    // Call the base createOperations and afterwards set some registry settings
    // so that the simulator finds its fonts and applications find the simulator
    component.createOperations();

    var perlRegKey;
    // registry key is used for checking if Strawberry Perl is already installed
    perlRegKey = installer.execute("REG", ["QUERY", "HKLM\\SOFTWARE\\Classes\\Perl_program_file\\shell\\Execute Perl Program\\command", "/s"])[0];

    var splitRegKey = perlRegKey.split(" ");
    var found = false;
    // loop trough the split regristry key and check if perl.exe is found
    for (i = 0; i < splitRegKey.length; i++) {
        if (splitRegKey[i].indexOf("perl.exe") !== -1) {
            print("Strawberry Perl registry key: " + perlRegKey);
            print("Strawberry Perl is already installed, will not be installed by Qt.");
            found = true;
        }
    }

    // Strawberry Perl will be installed
    if (!found) {
        print("Install Strawberry Perl.");
        var installStatus = component.addElevatedOperation("Execute", "{0,3010,1603, 5100}", "msiexec", "/i", "@TargetDir@\\Tools\\Perl52213_32\\strawberry-perl-5.22.1.3-32bit.msi", "/quiet", "UNDOEXECUTE", "msiexec", "/x", "@TargetDir@\\Tools\\Perl52213_32\\strawberry-perl-5.22.1.3-32bit.msi", "/q");
    }
}
