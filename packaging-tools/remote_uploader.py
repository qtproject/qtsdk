#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#############################################################################
#
# Copyright (C) 2022 The Qt Company Ltd.
# Contact: https://www.qt.io/licensing/
#
# This file is part of the release tools of the Qt Toolkit.
#
# $QT_BEGIN_LICENSE:GPL-EXCEPT$
# Commercial License Usage
# Licensees holding valid commercial Qt licenses may use this file in
# accordance with the commercial license agreement provided with the
# Software or, alternatively, in accordance with the terms contained in
# a written agreement between you and The Qt Company. For licensing terms
# and conditions see https://www.qt.io/terms-conditions. For further
# information use the contact form at https://www.qt.io/contact-us.
#
# GNU General Public License Usage
# Alternatively, this file may be used under the terms of the GNU
# General Public License version 3 as published by the Free Software
# Foundation with exceptions as appearing in the file LICENSE.GPL3-EXCEPT
# included in the packaging of this file. Please review the following
# information to ensure the GNU General Public License requirements will
# be met: https://www.gnu.org/licenses/gpl-3.0.html.
#
# $QT_END_LICENSE$
#
#############################################################################

import argparse
import os
import platform
import sys
from shutil import which
from subprocess import CalledProcessError, check_call


class RemoteUploaderError(Exception):
    pass


class RemoteUploader:
    """RemoteUploader can be used to upload given file(s) to remote network disk."""

    def __init__(self, dry_run, remote_server, remote_server_username, remote_base_path):
        self.dryRun = dry_run
        self.set_tools(remote_server, remote_server_username)
        self.remoteLogin = remote_server_username + '@' + remote_server
        self.remoteTargetBaseDir = remote_base_path
        self.init_finished = False

    def set_tools(self, remote_server, remote_server_username):
        self.ssh_cmd = ['ssh', '-o', 'GSSAPIAuthentication=no', '-o', 'StrictHostKeyChecking=no', remote_server_username + '@' + remote_server]
        system = platform.system().lower()
        if "windows" in system:
            if not which("scp"):
                raise RemoteUploaderError("'scp' tool not found from PATH")
            self.copy_cmd = ['scp']
        else:
            if not which("rsync"):
                raise RemoteUploaderError("'rsync' tool not found from PATH")
            self.copy_cmd = ['rsync']

    def init_snapshot_upload_path(self, project_name, version, snapshot_id):
        assert not self.init_finished, f"Already initialized as: {self.remoteTargetDir}"
        self.remoteTargetDir = self.remoteTargetBaseDir + "/" + project_name + "/" + version + "/" + snapshot_id
        self.remoteLatestLink = self.remoteTargetBaseDir + "/" + project_name + "/" + version + "/latest"
        self.init_finished = True
        self.ensure_remote_dir(self.remoteTargetDir)

    def init_upload_path(self, remote_path):
        assert not self.init_finished, f"Already initialized as: {self.remoteTargetDir}"
        self.remoteTargetDir = self.remoteTargetBaseDir + "/" + remote_path
        self.init_finished = True
        self.ensure_remote_dir(self.remoteTargetDir)

    def ensure_remote_dir(self, remote_dir):
        assert self.init_finished, "RemoteUploader not initialized!"
        print(f"Creating remote directory: {remote_dir}")
        cmd = self.ssh_cmd + ['mkdir', '-p', remote_dir]
        print("Executing: ", ' '.join(cmd))
        if not self.dryRun:
            check_call(cmd, timeout=60)  # give it 60s

    def _copy_to_remote(self, file_name, dest_dir_name):
        """Copy the given file to destDirName which is relative to remoteBasePath."""
        assert self.init_finished, "RemoteUploader not initialized!"
        remoteDestination = self.remoteLogin + ':' + self.remoteTargetDir
        if dest_dir_name:
            remoteDestination = remoteDestination + '/' + dest_dir_name + '/'
            if "windows" in platform.system().lower():
                self.ensure_remote_dir(self.remoteTargetDir + '/' + dest_dir_name + '/')
        print(f"Copying [{file_name}] to [{remoteDestination}]")
        cmd = self.copy_cmd + [file_name, remoteDestination]
        print("Executing: ", ' '.join(cmd))
        if not self.dryRun:
            check_call(cmd, timeout=60 * 10)  # give it 10 mins

    def copy_to_remote(self, path: str, dest_dir_name=""):
        items = [path] if os.path.isfile(path) else [os.path.join(path, x) for x in os.listdir(path)]
        for item in items:
            self._copy_to_remote(item, dest_dir_name)

    def update_latest_symlink(self, force_update=True):
        assert self.init_finished, "RemoteUploader not initialized!"
        print(f"Creating remote symlink: [{self.remoteLatestLink}] -> [{self.remoteTargetDir}]")
        options = ["-sfn"] if force_update else ["-sn"]
        try:
            cmd = self.ssh_cmd + ['ln'] + options + [self.remoteTargetDir, self.remoteLatestLink]
            print("Executing: ", ' '.join(cmd))
            if not self.dryRun:
                check_call(cmd, timeout=60)  # give it 60s
        except CalledProcessError:
            print("Failed to execute: ", ' '.join(cmd))
            raise


def main() -> None:
    """Main"""
    parser = argparse.ArgumentParser(prog="Copy given file or directory contents to remote.")
    parser.add_argument("--dry-run", dest="dry_run", action='store_true', help="Dry-run the command.")
    parser.add_argument("--source", dest="source", type=str, required=True, help="What to copy to remote. Can be a file or a directory")
    parser.add_argument("--remote-server", dest="remote_server", type=str, default=os.getenv("REMOTE_SERVER"), help="Remote server name/address.")
    parser.add_argument("--remote-server-user", dest="remote_server_user", type=str, default=os.getenv("REMOTE_SERVER_USER"), help="Remote server user name.")
    parser.add_argument("--remote-server-base-path", dest="remote_server_base_path", type=str, default=os.getenv("REMOTE_SERVER_BASE_PATH"), help="Remote server base path.")
    parser.add_argument("--project-name", dest="project_name", type=str, required=True, help="Project name")
    parser.add_argument("--project-version", dest="project_version", type=str, required=True, help="Project version")
    parser.add_argument("--project-snapshot-id", dest="project_snapshot_id", type=str, required=True, help="Project snapshot id")
    parser.add_argument("--subdir-name", dest="subdir_name", type=str, required=False, help="If needed create a subdirectory where to upload the source file(s).")

    args = parser.parse_args(sys.argv[1:])

    uploader = RemoteUploader(args.dry_run, args.remote_server, args.remote_server_user, args.remote_server_base_path)
    uploader.init_snapshot_upload_path(args.project_name, args.project_version, args.project_snapshot_id)
    uploader.copy_to_remote(args.source, args.subdir_name)
    uploader.update_latest_symlink()


if __name__ == "__main__":
    main()
