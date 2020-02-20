#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

import testhelpers
import os
import io
import unittest
import tempfile
import tarfile
from socket import getaddrinfo
from installer_utils import cd, PackagingError, get_extract_cmd, extract_archive, download_archive, is_valid_url_path

packageServer = "ci-files02-hki.intra.qt.io"


def _isInternalFileServerReachable():
    try:
        getaddrinfo(packageServer, 80)
    except Exception:
        return False
    return True


class TestInstallerUtils(unittest.TestCase):

    @testhelpers.asyncio_test
    async def test_cd(self) -> None:
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory(dir=cwd) as tmpBaseDir:
            with cd(tmpBaseDir):
                self.assertEqual(tmpBaseDir, os.getcwd())
        self.assertEqual(cwd, os.getcwd())

    @testhelpers.asyncio_test_parallel_data(
        ("https://www.qt.io", False),
        ("https://", False),
        (None, False),
        ("https://www.qt.io/some/file.tar.gz", True),
    )
    async def test_is_valid_url_path(self, url: str, expectedResult: bool) -> None:
        self.assertEqual(is_valid_url_path(url), expectedResult,
                         "URL: {0} - expected result: {1} - result was: {2}".format(url, expectedResult, not expectedResult))

    @testhelpers.asyncio_test_parallel_data(
        ("https://www.qt.io/some/file.zip", "7z"),
        ("https://www.qt.io/some/file.tar.gz", "tar"),
        ("https://www.qt.io/some/file.7z", "7z"),
        ("https://www.qt.io/some/file.tgz", "tar")
    )
    async def test_valid_extractor(self, archive: str, expectedExtractor: str) -> None:
        extractCmd = get_extract_cmd(archive)
        self.assertEqual(extractCmd[0], expectedExtractor, "Not a valid extractor Callable obtained for: {0}".format(archive))

    @testhelpers.asyncio_test
    async def test_invalid_extractor(self) -> None:
        with self.assertRaises(PackagingError):
            get_extract_cmd("https://www.qt.io/some/file.foo.bar")

    @testhelpers.asyncio_test
    async def test_extract_archive(self) -> None:
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as tmpBaseDir:
            # create some test paths
            tempPath = os.path.join("foo", "bar")
            absoluteTempPath = os.path.join(tmpBaseDir, tempPath)
            os.makedirs(absoluteTempPath)
            # create tmp file
            tempFileName = "foobar.txt"
            tempFilePath = os.path.join(absoluteTempPath, tempFileName)
            with open(tempFilePath, 'w+') as f:
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

    @testhelpers.asyncio_test
    @unittest.skipUnless(_isInternalFileServerReachable(), "Skipping because '{0}' is not accessible".format(packageServer))
    async def test_download_archive(self) -> None:
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as tmpBaseDir:
            downloadedFile = download_archive("http://{0}/packages/jenkins/python/src/Python-3.8.1.tgz".format(packageServer), tmpBaseDir)
            self.assertTrue(os.path.isfile(downloadedFile))


if __name__ == '__main__':
    unittest.main()
