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

import io
import os
import tarfile
import unittest
from tempfile import TemporaryDirectory

from installer_utils import (
    PackagingError,
    cd,
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
    async def test_cd(self) -> None:
        cwd = os.getcwd()
        with TemporaryDirectory(dir=cwd) as tmpBaseDir:
            with cd(tmpBaseDir):
                self.assertEqual(tmpBaseDir, os.getcwd())
        self.assertEqual(cwd, os.getcwd())

    @asyncio_test_parallel_data(
        ("https://www.qt.io", False),
        ("https://", False),
        (None, False),
        ("https://www.qt.io/some/file.tar.gz", True),
    )
    async def test_is_valid_url_path(self, url: str, expected_result: bool) -> None:
        self.assertEqual(is_valid_url_path(url), expected_result,
                         f"URL: {url} - expected result: {expected_result} - result was: {not expected_result}")

    @asyncio_test_parallel_data(
        ("https://www.qt.io/some/file.zip", "7z"),
        ("https://www.qt.io/some/file.tar.gz", "tar"),
        ("https://www.qt.io/some/file.7z", "7z"),
        ("https://www.qt.io/some/file.tgz", "tar")
    )
    async def test_valid_extractor(self, archive: str, expected_extractor: str) -> None:
        extractCmd = get_extract_cmd(archive)
        self.assertEqual(extractCmd[0], expected_extractor, f"Not a valid extractor Callable obtained for: {archive}")

    @asyncio_test
    async def test_invalid_extractor(self) -> None:
        with self.assertRaises(PackagingError):
            get_extract_cmd("https://www.qt.io/some/file.foo.bar")

    @asyncio_test
    async def test_extract_archive(self) -> None:
        with TemporaryDirectory(dir=os.getcwd()) as tmpBaseDir:
            # create some test paths
            tempPath = os.path.join("foo", "bar")
            absoluteTempPath = os.path.join(tmpBaseDir, tempPath)
            os.makedirs(absoluteTempPath)
            # create tmp file
            tempFileName = "foobar.txt"
            tempFilePath = os.path.join(absoluteTempPath, tempFileName)
            with open(tempFilePath, 'w+', encoding="utf-8") as f:
                f.write("\n")
            self.assertTrue(os.path.isfile(tempFilePath))

            # create fake tar archive
            tarArchivePath = os.path.join(tmpBaseDir, "foobar.tar")
            with tarfile.open(tarArchivePath, "w") as tarFile:
                with open(tempFilePath, mode='rb') as _tempFile:
                    fileData = _tempFile.read()
                    tarFile.addfile(tarfile.TarInfo(os.path.join(tempPath, tempFileName)), io.BytesIO(fileData))

            destDir = os.path.join(tmpBaseDir, "dest_dir")
            await extract_archive(tarArchivePath, destDir)
            self.assertTrue(os.path.isfile(os.path.join(destDir, tempPath, "foobar.txt")))

    @unittest.skipUnless(is_internal_file_server_reachable(),
                         "Skipping because file server is not accessible")
    @asyncio_test
    async def test_download_archive(self) -> None:
        with TemporaryDirectory(dir=os.getcwd()) as tmpBaseDir:
            pkg_srv = get_pkg_value("PACKAGE_STORAGE_SERVER_PATH_HTTP")
            test_file_url = pkg_srv + "/archive/packaging/qtsdk_testing.txt"
            downloadedFile = download_archive(test_file_url, tmpBaseDir)
            self.assertTrue(os.path.isfile(downloadedFile))


if __name__ == '__main__':
    unittest.main()
