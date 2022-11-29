#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#############################################################################
#
# Copyright (C) 2023 The Qt Company Ltd.
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

import unittest
from getpass import getuser
from pathlib import Path
from typing import Dict

from ddt import data, ddt, unpack  # type: ignore
from temppathlib import TemporaryDirectory

from build_wrapper import init_snapshot_dir_and_upload_files


@ddt
class TestBuildWrapper(unittest.TestCase):

    @data(  # type: ignore
        ("test-project-name", "1.0", "1234567890"),
        ("test-project-name-2", "snapshots/1.2.3", "1234567890"),
        ("test-project-name", "1.0", "1234567890", "mysubdir"),
        ("test-project-name-2", "snapshots/1.2.3", "1234567890", "mysubdir"),
    )
    @unpack  # type: ignore
    def test_init_snapshot_dir_and_upload_files(
            self, project_name: str, version_branch: str, build_number: str, subdir: str = ""
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            work_dir = Path.cwd()
            option_dict: Dict[str, str] = {
                'WORK_DIR': str(work_dir), 'SSH_COMMAND': 'ssh', 'SCP_COMMAND': 'scp',
                'PACKAGE_STORAGE_SERVER_ADDR': getuser() + '@127.0.0.1',
                'PACKAGE_STORAGE_SERVER_BASE_DIR': str(temp_dir.path)
            }
            files_to_upload = [x.name for x in work_dir.glob('*.sh')]
            init_snapshot_dir_and_upload_files(
                option_dict, project_name, version_branch, build_number, files_to_upload, subdir
            )

            remote_path_base = temp_dir.path / project_name / version_branch
            remote_path_snapshot_dir = remote_path_base / build_number
            remote_path_latest_link = remote_path_base / 'latest'
            self.assertTrue(remote_path_base.is_dir())
            self.assertTrue(remote_path_snapshot_dir.is_dir())
            self.assertTrue(remote_path_latest_link.is_symlink())

            search_dir = remote_path_latest_link / subdir
            uploaded_files = [x.name for x in search_dir.glob('*.sh')]
            self.assertListEqual(sorted(files_to_upload), sorted(uploaded_files))


if __name__ == '__main__':
    unittest.main()
