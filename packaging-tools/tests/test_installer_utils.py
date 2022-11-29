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

import io
import os
import tarfile
import unittest
from pathlib import Path

from temppathlib import TemporaryDirectory

from installer_utils import (
    PackagingError,
    ch_dir,
    download_archive,
    extract_archive,
    get_extract_cmd,
    is_valid_url_path,
)
from read_remote_config import get_pkg_value
from tests.testhelpers import (
    asyncio_test,
    asyncio_test_parallel_data,
    is_internal_file_server_reachable,
)


class TestInstallerUtils(unittest.TestCase):

    @asyncio_test
    async def test_ch_dir(self) -> None:
        with TemporaryDirectory() as tmp_base_dir:
            with ch_dir(str(tmp_base_dir.path)):
                self.assertEqual(tmp_base_dir.path, Path.cwd())

    @asyncio_test_parallel_data(  # type: ignore
        ("https://www.qt.io", False),
        ("https://", False),
        (None, False),
        ("https://www.qt.io/some/file.tar.gz", True),
    )
    async def test_is_valid_url_path(self, url: str, expected_result: bool) -> None:
        self.assertEqual(is_valid_url_path(url), expected_result,
                         f"URL: {url} - expected result: {expected_result} - result was: {not expected_result}")

    @asyncio_test_parallel_data(  # type: ignore
        ("https://www.qt.io/some/file.zip", "7z"),
        ("https://www.qt.io/some/file.tar.gz", "tar"),
        ("https://www.qt.io/some/file.7z", "7z"),
        ("https://www.qt.io/some/file.tgz", "tar")
    )
    async def test_valid_extractor(self, archive: str, expected_extractor: str) -> None:
        extract_cmd = get_extract_cmd(archive)
        self.assertEqual(extract_cmd[0], expected_extractor, f"Not a valid extractor Callable obtained for: {archive}")

    @asyncio_test
    async def test_invalid_extractor(self) -> None:
        with self.assertRaises(PackagingError):
            get_extract_cmd("https://www.qt.io/some/file.foo.bar")

    @asyncio_test
    async def test_extract_archive(self) -> None:
        with TemporaryDirectory() as tmp_base_dir:
            # create some test paths
            temp_path = Path("foo", "bar")
            absolute_temp_path = tmp_base_dir.path / temp_path
            absolute_temp_path.mkdir(parents=True)
            # create tmp file
            temp_file_name = "foobar.txt"
            temp_file_path = absolute_temp_path / temp_file_name
            with temp_file_path.open('w+', encoding="utf-8") as handle:
                handle.write("\n")
            self.assertTrue(temp_file_path.is_file())

            # create fake tar archive
            tar_archive_path = tmp_base_dir.path / "foobar.tar"
            with tarfile.open(tar_archive_path, "w") as tar_file:
                with temp_file_path.open(mode='rb') as _temp_file:
                    file_data = _temp_file.read()
                    tar_file.addfile(
                        tarfile.TarInfo(str(temp_path / temp_file_name)), io.BytesIO(file_data)
                    )

            dest_dir = tmp_base_dir.path / "dest_dir"
            await extract_archive(str(tar_archive_path), str(dest_dir))
            self.assertTrue((dest_dir / temp_path / "foobar.txt").is_file())

    @unittest.skipUnless(is_internal_file_server_reachable(),
                         "Skipping because file server is not accessible")
    @asyncio_test
    async def test_download_archive(self) -> None:
        with TemporaryDirectory() as tmp_base_dir:
            pkg_srv = get_pkg_value("PACKAGE_STORAGE_SERVER_PATH_HTTP")
            test_file_url = pkg_srv + "/archive/packaging/qtsdk_testing.txt"
            downloaded_file = download_archive(test_file_url, str(tmp_base_dir.path))
            self.assertTrue(os.path.isfile(downloaded_file))


if __name__ == '__main__':
    unittest.main()
