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
from subprocess import CalledProcessError

from logging_util import init_logger
from runner import run_cmd

log = init_logger(__name__, debug_mode=False)


class RemoteUploaderError(Exception):
    pass


class RemoteUploader:
    """RemoteUploader can be used to upload given file(s) to remote network disk."""

    def __init__(self, dry_run: bool, remote_server: str, remote_server_username: str, remote_base_path: str):
        self.dry_run = dry_run
        self.set_tools(remote_server, remote_server_username)
        self.remote_latest_link = ""
        self.remote_login = remote_server_username + '@' + remote_server
        self.remote_target_dir = ""
        self.remote_target_base_dir = remote_base_path
        self.init_finished = False

    def set_tools(self, remote_server: str, remote_server_username: str) -> None:
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

    def init_snapshot_upload_path(self, project_name: str, version: str, snapshot_id: str) -> None:
        assert not self.init_finished, f"Already initialized as: {self.remote_target_dir}"
        self.remote_target_dir = self.remote_target_base_dir + "/" + project_name + "/" + version + "/" + snapshot_id
        self.remote_latest_link = self.remote_target_base_dir + "/" + project_name + "/" + version + "/latest"
        self.init_finished = True
        self.ensure_remote_dir(self.remote_target_dir)

    def init_upload_path(self, remote_path: str) -> None:
        assert not self.init_finished, f"Already initialized as: {self.remote_target_dir}"
        self.remote_target_dir = self.remote_target_base_dir + "/" + remote_path
        self.init_finished = True
        self.ensure_remote_dir(self.remote_target_dir)

    def ensure_remote_dir(self, remote_dir: str) -> None:
        assert self.init_finished, "RemoteUploader not initialized!"
        log.info("Creating remote directory: %s", remote_dir)
        cmd = self.ssh_cmd + ["mkdir", "-p", remote_dir]
        if not self.dry_run:
            run_cmd(cmd=cmd, timeout=60)  # give it 60s

    def _copy_to_remote(self, file_name: str, dest_dir_name: str) -> None:
        """Copy the given file to dest_dir_name which is relative to remote_base_path."""
        assert self.init_finished, "RemoteUploader not initialized!"
        remote_destination = self.remote_login + ':' + self.remote_target_dir
        if dest_dir_name:
            remote_destination = remote_destination + '/' + dest_dir_name + '/'
            if "windows" in platform.system().lower():
                self.ensure_remote_dir(self.remote_target_dir + '/' + dest_dir_name + '/')
        log.info("Copying [%s] to [%s]", file_name, remote_destination)
        cmd = self.copy_cmd + [file_name, remote_destination]
        if not self.dry_run:
            run_cmd(cmd=cmd, timeout=60 * 10)  # give it 10 minutes

    def copy_to_remote(self, path: str, dest_dir_name: str = "") -> None:
        items = [path] if os.path.isfile(path) else [os.path.join(path, x) for x in os.listdir(path)]
        for item in items:
            self._copy_to_remote(item, dest_dir_name)

    def update_latest_symlink(self, force_update: bool = True) -> None:
        assert self.init_finished, "RemoteUploader not initialized!"
        log.info("Create remote symlink: %s -> %s", self.remote_latest_link, self.remote_target_dir)
        options = ["-sfn"] if force_update else ["-sn"]
        try:
            args = ['ln'] + options + [self.remote_target_dir, self.remote_latest_link]
            cmd = self.ssh_cmd + args
            if not self.dry_run:
                run_cmd(cmd=cmd, timeout=60)  # give it 60s
        except CalledProcessError as error:
            log.exception("Failed to execute: %s", " ".join(cmd), exc_info=error)
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
