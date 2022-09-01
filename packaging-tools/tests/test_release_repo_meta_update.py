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
from tempfile import TemporaryDirectory
from typing import List

from ddt import ddt  # type: ignore

from release_repo_meta_update import (
    IfwRepoUpdateError,
    backup_suffix,
    check_repos_which_can_be_updated,
    convert_suffix,
    create_converted_repositories,
    scan_repositories,
    swap_repositories,
)
from tests.testhelpers import asyncio_test


@ddt
class TestReleaseRepoMetaUpdate(unittest.TestCase):
    paths = None  # type: List[str]
    non_migrated_paths = None  # type: List[str]
    mixed_migrated_paths = None  # type: List[str]

    @classmethod
    def setUpClass(cls) -> None:
        cls.paths = [
            "repo1/Updates.xml",
            "repo2/Updates.xml",
            "repo2" + convert_suffix + "/Updates.xml",
            "repo2" + convert_suffix + "/123456_meta.7z",
            "repo3/Updates.xml",
            "repo3" + convert_suffix + "/Updates.xml",
            "repo3" + convert_suffix + "/123456_meta.7z",
            "repo4/Updates.xml",
            "repo5/Updates.xml",
            "repo5/123456_meta.7z",
            "repo6/Updates.xml",
            "repo7/Updates.xml",
            "repo7/123456_meta.7z",
            "repo7" + convert_suffix + "/Updates.xml",
            "repo7" + convert_suffix + "/123456_meta.7z",
            "repo8/Updates.xml",
            "repo9/Updates.xml",
            "repo9" + convert_suffix + "/Updates.xml",
            "repo9" + convert_suffix + "/",  # meta.7z missing
            "repo10" + backup_suffix + "123456"
        ]
        cls.non_migrated_paths = [
            "repo1/Updates.xml",
            "repo2/sub2/Updates.xml",
            "repo3/sub3/subsub3/Updates.xml",
            "repo4/Updates.xml",
            "repo5/Updates.xml",
        ]
        cls.mixed_migrated_paths = [
            "repo1/Updates.xml",
            "repo1" + convert_suffix + "/Updates.xml",
            "repo2/sub2/Updates.xml",
            "repo3/sub3/subsub3/Updates.xml",
            "repo3/sub3/subsub3" + convert_suffix + "/Updates.xml",
            "repo4/Updates.xml",
            "repo5/Updates.xml",
        ]

    def _write_test_repo(self, tmp_base_dir: str, paths: List[str]) -> None:
        for path in paths:
            tmp = os.path.join(tmp_base_dir, path)
            os.makedirs(os.path.dirname(tmp), exist_ok=True)
            if tmp.endswith((".xml", ".7z")):
                with open(tmp, 'w+', encoding="utf-8") as f:
                    f.write("\n")

    @asyncio_test
    async def test_scan_repositories(self) -> None:
        with TemporaryDirectory(dir=os.getcwd(), prefix="_repo_tmp_") as tmp_base_dir:
            self._write_test_repo(tmp_base_dir, self.paths)

            done_repos, pending_repos, unconverted_repos, broken_repos = scan_repositories(tmp_base_dir)
            self.assertListEqual(sorted([repo.split(tmp_base_dir)[-1] for repo in broken_repos]),
                                 sorted(["/repo9" + convert_suffix]))
            self.assertListEqual(sorted([repo.split(tmp_base_dir)[-1] for repo in unconverted_repos]),
                                 sorted(["/repo1", "/repo2", "/repo3", "/repo4", "/repo6", "/repo8", "/repo9"]))
            self.assertListEqual(sorted([repo.split(tmp_base_dir)[-1] for repo in pending_repos]),
                                 sorted(["/repo2" + convert_suffix, "/repo3" + convert_suffix,
                                         "/repo7" + convert_suffix]))
            self.assertListEqual(sorted([repo.split(tmp_base_dir)[-1] for repo in done_repos]),
                                 sorted(["/repo5", "/repo7"]))

    @asyncio_test
    async def test_check_repos_which_can_be_updated(self) -> None:
        with TemporaryDirectory(dir=os.getcwd(), prefix="_repo_tmp_") as tmp_base_dir:
            self._write_test_repo(tmp_base_dir, self.paths)
            done_repos, pending_repos, unconverted_repos, _ = scan_repositories(tmp_base_dir)

            updatable_repos, existing_pending_repos = check_repos_which_can_be_updated(done_repos + pending_repos + unconverted_repos)
            self.assertListEqual(sorted([repo.split(tmp_base_dir)[-1] for repo in updatable_repos]),
                                 sorted(["/repo1", "/repo4", "/repo5", "/repo6", "/repo8"]))
            self.assertListEqual(sorted([repo.split(tmp_base_dir)[-1] for repo in existing_pending_repos]),
                                 sorted(["/repo2", "/repo3", "/repo7", "/repo9"]))

    @asyncio_test
    async def test_swap_repositories_invalid(self) -> None:
        with TemporaryDirectory(dir=os.getcwd(), prefix="_repo_tmp_") as tmp_base_dir:
            self._write_test_repo(tmp_base_dir, self.paths)
            unconverted_repos = scan_repositories(tmp_base_dir)[2]
            with self.assertRaises(IfwRepoUpdateError):
                await create_converted_repositories(repogen="foobar-repogen", repositories_to_migrate=unconverted_repos,
                                                    dry_run=True)

    @asyncio_test
    async def test_swap_repositories_valid(self) -> None:
        with TemporaryDirectory(dir=os.getcwd(), prefix="_repo_tmp_") as tmp_base_dir:
            self._write_test_repo(tmp_base_dir, self.non_migrated_paths)
            unconverted_repos = scan_repositories(tmp_base_dir)[2]
            successful_conversions, failed_conversions = await create_converted_repositories(repogen="foobar-repogen",
                                                                                             repositories_to_migrate=unconverted_repos,
                                                                                             dry_run=True)
            self.assertTrue(not failed_conversions)
            # as it was dry-run we need to create the dummy migrated repo directories here
            for _, migrated_repo in successful_conversions.items():
                os.makedirs(migrated_repo)
            operations_ok, operations_nok = swap_repositories(successful_conversions)
            self.assertTrue(not operations_nok)
            self.assertListEqual(sorted(successful_conversions.keys()), sorted(operations_ok.keys()))
            for _, items in operations_ok.items():
                backup_repo_name = items[1]
                self.assertTrue(backup_suffix in backup_repo_name)


if __name__ == '__main__':
    unittest.main()
