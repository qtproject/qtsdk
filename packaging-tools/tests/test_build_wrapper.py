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

import os
import unittest
from getpass import getuser
from glob import glob
from tempfile import TemporaryDirectory
from typing import Dict

from ddt import data, ddt, unpack  # type: ignore

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
            option_dict: Dict[str, str] = {
                'WORK_DIR': os.getcwd(), 'SSH_COMMAND': 'ssh', 'SCP_COMMAND': 'scp',
                'PACKAGE_STORAGE_SERVER_ADDR': getuser() + '@127.0.0.1',
                'PACKAGE_STORAGE_SERVER_BASE_DIR': temp_dir
            }
            files_to_upload = [os.path.basename(x) for x in glob('./*.sh')]
            init_snapshot_dir_and_upload_files(
                option_dict, project_name, version_branch, build_number, files_to_upload, subdir
            )

            remote_path_base = os.path.join(temp_dir, project_name, version_branch)
            remote_path_snapshot_dir = os.path.join(remote_path_base, build_number)
            remote_path_latest_link = os.path.join(remote_path_base, 'latest')
            self.assertTrue(os.path.isdir(remote_path_base))
            self.assertTrue(os.path.isdir(remote_path_snapshot_dir))
            self.assertTrue(os.path.islink(remote_path_latest_link))

            search_dir = os.path.join(remote_path_latest_link, subdir, '*.sh')
            uploaded_files = [os.path.basename(x) for x in glob(search_dir)]
            self.assertListEqual(sorted(files_to_upload), sorted(uploaded_files))


if __name__ == '__main__':
    unittest.main()
