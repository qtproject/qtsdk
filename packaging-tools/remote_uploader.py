#!/usr/bin/env python
#############################################################################
##
## Copyright (C) 2019 The Qt Company Ltd.
## Contact: https://www.qt.io/licensing/
##
## This file is part of the release tools of the Qt Toolkit.
##
## $QT_BEGIN_LICENSE:GPL-EXCEPT$
## Commercial License Usage
## Licensees holding valid commercial Qt licenses may use this file in
## accordance with the commercial license agreement provided with the
## Software or, alternatively, in accordance with the terms contained in
## a written agreement between you and The Qt Company. For licensing terms
## and conditions see https://www.qt.io/terms-conditions. For further
## information use the contact form at https://www.qt.io/contact-us.
##
## GNU General Public License Usage
## Alternatively, this file may be used under the terms of the GNU
## General Public License version 3 as published by the Free Software
## Foundation with exceptions as appearing in the file LICENSE.GPL3-EXCEPT
## included in the packaging of this file. Please review the following
## information to ensure the GNU General Public License requirements will
## be met: https://www.gnu.org/licenses/gpl-3.0.html.
##
## $QT_END_LICENSE$
##
#############################################################################

import sh


class RemoteUploader:
    """RemoteUploader can be used to upload given file(s) to remote network disk."""

    def __init__(self, dryRun, remoteServer, remoteServerUserName, remoteBasePath, branch, projectName):
        self.dryRun = dryRun
        self.ssh = sh.ssh.bake("-o", "GSSAPIAuthentication=no", "-o", "StrictHostKeyChecking=no", remoteServerUserName + '@' + remoteServer)
        self.remoteLogin = remoteServerUserName + '@' + remoteServer
        self.remoteTargetBaseDir = remoteBasePath + '/' + projectName + '/' + branch + '/'
        self.remoteTargetDir = ''

    def initRemoteSnapshotDir(self, buildId):
        """Create snapshot directory on the remote disk containing the basic directory structure required by installer configs."""
        self.remoteTargetDir = self.remoteTargetBaseDir + buildId
        self.releaseSymbolsDir = '/debug_information'
        self.ensureRemoteDir(self.remoteTargetDir + self.releaseSymbolsDir)

    def ensureRemoteDir(self, remoteDir):
        print("Creating remote directory: {0}".format(remoteDir))
        if self.dryRun:
            return
        self.ssh.mkdir("-p", remoteDir)

    def copyToRemote(self, fileName, destDirName):
        """Copy the given file to destDirName which is relative to remoteBasePath."""
        remoteDestination = self.remoteLogin + ':' + self.remoteTargetDir
        if destDirName:
            remoteDestination = remoteDestination + '/' + destDirName + '/'
        print("Copying [{0}] to [{1}]".format(fileName, remoteDestination))
        self.remoteCopy = sh.rsync.bake(fileName, remoteDestination)
        if self.dryRun:
            return
        self.remoteCopy()
