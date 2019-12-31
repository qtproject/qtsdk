#!/usr/bin/env python
#############################################################################
##
## Copyright (C) 2020 The Qt Company Ltd.
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

import os
import sys
import argparse
import platform
try:
    import sh
except ImportError:
    # fallback: emulate the sh API with pbs
    import pbs
    class Sh(object):
        def __getattr__(self, attr):
            return pbs.Command(attr)
    sh = Sh()


class RemoteUploader:
    """RemoteUploader can be used to upload given file(s) to remote network disk."""

    def __init__(self, dryRun, remoteServer, remoteServerUserName, remoteBasePath):
        self.dryRun = dryRun
        self.ssh = sh.ssh.bake("-o", "GSSAPIAuthentication=no", "-o", "StrictHostKeyChecking=no", remoteServerUserName + '@' + remoteServer)
        self.copyTool = sh.scp.bake if platform.system().lower() == "windows" else sh.rsync.bake
        self.remoteLogin = remoteServerUserName + '@' + remoteServer
        self.remoteTargetBaseDir = remoteBasePath
        self.init_finished = False

    def init_snapshot_upload_path(self, projectName, version, snapshotId):
        assert not self.init_finished, "Already initialized as: {0}".format(self.remoteTargetDir)
        self.remoteTargetDir = self.remoteTargetBaseDir + "/" + projectName + "/" + version + "/" + snapshotId
        self.remoteLatestLink = self.remoteTargetBaseDir + "/" + projectName + "/" + version + "/latest"
        self.init_finished = True
        self.ensureRemoteDir(self.remoteTargetDir)

    def init_upload_path(self, remotePath):
        assert not self.init_finished, "Already initialized as: {0}".format(self.remoteTargetDir)
        self.remoteTargetDir = self.remoteTargetBaseDir + "/" + remotePath
        self.init_finished = True
        self.ensureRemoteDir(self.remoteTargetDir)

    def ensureRemoteDir(self, remoteDir):
        assert self.init_finished, "RemoteUploader not initialized!"
        print("Creating remote directory: {0}".format(remoteDir))
        if self.dryRun:
            return
        self.ssh.mkdir("-p", remoteDir)

    def _copyToRemote(self, fileName, destDirName):
        assert self.init_finished, "RemoteUploader not initialized!"
        """Copy the given file to destDirName which is relative to remoteBasePath."""
        remoteDestination = self.remoteLogin + ':' + self.remoteTargetDir
        if destDirName:
            remoteDestination = remoteDestination + '/' + destDirName + '/'
        print("Copying [{0}] to [{1}]".format(fileName, remoteDestination))
        remoteCopy = self.copyTool(fileName, remoteDestination)
        if self.dryRun:
            return
        remoteCopy()

    def copyToRemote(self, path: str, destDirName=""):
        items = [path] if os.path.isfile(path) else [os.path.join(path, x) for x in os.listdir(path)]
        for item in items:
            self._copyToRemote(item, destDirName)

    def updateLatestSymlink(self, forceUpdate=True):
        assert self.init_finished, "RemoteUploader not initialized!"
        print("Creating remote symlink: [{0}] -> [{1}]".format(self.remoteLatestLink, self.remoteTargetDir))
        if not self.dryRun:
            options = "-sfn" if forceUpdate else "-sn"
            try:
                self.ssh.ln(options, self.remoteTargetDir, self.remoteLatestLink)
            except sh.ErrorReturnCode_1:
                print("Symbolic link already exists.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="Copy given file or directory contents to remote.")
    parser.add_argument("--dry-run", dest="dry_run", action='store_true', help="Dry-run the command.")
    parser.add_argument("--source", dest="source", type=str, required=True, help="What to copy to remote. Can be a file or a directory")
    parser.add_argument("--remote-server", dest="remote_server", type=str, default=os.getenv("REMOTE_SERVER"), help="Remote server name/address.")
    parser.add_argument("--remote-server-user", dest="remote_server_user", type=str, default=os.getenv("REMOTE_SERVER_USER"), help="Remote server user name.")
    parser.add_argument("--remote-server-base-path", dest="remote_server_base_path", type=str, default=os.getenv("REMOTE_SERVER_BASE_PATH"), help="Remote server base path.")
    parser.add_argument("--project-name", dest="project_name", type=str, required=True, help="Project name")
    parser.add_argument("--project-version", dest="project_version", type=str, required=True, help="Project version")
    parser.add_argument("--project-snapshot-id", dest="project_snapshot_id", type=str, required=True, help="Project snapshot id")

    args = parser.parse_args(sys.argv[1:])

    uploader = RemoteUploader(args.dry_run, args.remote_server, args.remote_server_user, args.remote_server_base_path)
    uploader.init_snapshot_upload_path(args.project_name, args.project_version, args.project_snapshot_id)
    uploader.copyToRemote(args.source)
    uploader.updateLatestSymlink()

