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
from configparser import ConfigParser
from shutil import rmtree
from tempfile import TemporaryDirectory
from typing import List

from ddt import ddt  # type: ignore

from installer_utils import PackagingError
from read_remote_config import get_pkg_value
from release_repo_updater import (
    append_to_task_filters,
    build_online_repositories,
    check_repogen_output,
    create_remote_repository_backup,
    ensure_ext_repo_paths,
    format_task_filters,
    has_connection_error,
    parse_ext,
    remote_file_exists,
    reset_new_remote_repository,
    string_to_bool,
    upload_ifw_to_remote,
    upload_pending_repository_content,
)
from release_task_reader import parse_data
from tests.testhelpers import (
    asyncio_test,
    asyncio_test_parallel_data,
    isInternalFileServerReachable,
)


def _write_dummy_file(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w+') as f:
        f.write("\n")


def _write_package_xml(path: str, version: str, releaseDate: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w+') as f:
        f.write("<?xml version=\"1.0\"?>\n")
        f.write("<Package>\n")
        f.write("  <Name>qt.foo.bar1</Name>\n")
        f.write("  <DisplayName>Test</DisplayName>\n")
        f.write("  <Description>Test</Description>\n")
        f.write("  <Version>{0}</Version>\n".format(version))
        f.write("  <ReleaseDate>{0}</ReleaseDate>\n".format(releaseDate))
        f.write("</Package>\n")


def _write_updates_xml(path: str, version: str, releaseDate: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w+') as f:
        f.write("<Updates>\n")
        f.write("  <ApplicationName>{AnyApplication}</ApplicationName>\n")
        f.write("  <ApplicationVersion>1.0.0</ApplicationVersion>\n")
        f.write("  <Checksum>false</Checksum>\n")
        f.write("  <PackageUpdate>\n")
        f.write("    <Name>qt.foo.bar1</Name>\n")
        f.write("    <DisplayName>Foo bar</DisplayName>\n")
        f.write("    <Description>Foo and bar</Description>\n")
        f.write("    <Version>{0}</Version>\n".format(version))
        f.write("    <ReleaseDate>{0}</ReleaseDate>\n".format(releaseDate))
        f.write("    <DownloadableArchives/>\n")
        f.write("    <UpdateFile CompressedSize=\"0\" OS=\"Any\" UncompressedSize=\"0\"/>\n")
        f.write("    <SHA1>c1559cbb0f0983909f7229dc79dfdf7eab46cd52</SHA1>\n")
        f.write("  </PackageUpdate>\n")
        f.write("</Updates>\n")


async def _get_repogen() -> str:
    pkgsrv = get_pkg_value("PACKAGE_STORAGE_SERVER_PATH_HTTP")
    ifwTools = (
        f"{pkgsrv}/archive/ifw/enterprise/unifiedqt/4.3.0/tqtc-installer-framework-Linux-RHEL_7_6-"
        "GCC-Linux-RHEL_7_6-X86_64.7z"
    )
    server = "127.0.0.1"
    serverHome = os.path.expanduser("~")
    return await upload_ifw_to_remote(ifwTools, server, serverHome)


@ddt
class TestReleaseRepoUpdater(unittest.TestCase):
    server = None  # type: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = "127.0.0.1"

    @asyncio_test
    async def test_remote_file_exists(self):
        self.assertTrue(remote_file_exists(self.server, os.path.abspath(__file__)))
        self.assertFalse(remote_file_exists(self.server, "/some/bogus/directory/foo.txt"))

    @unittest.skipUnless(isInternalFileServerReachable(), "Skipping because file server is not accessible")
    @asyncio_test
    async def test_upload_ifw_to_remote(self) -> None:
        try:
            repogen = await _get_repogen()
        finally:
            self.assertTrue(os.path.isfile(repogen))
            rmtree(os.path.dirname(repogen))

    @asyncio_test
    async def test_upload_pending_repository_content(self) -> None:
        with TemporaryDirectory(dir=os.getcwd(), prefix="_repo_tmp_") as tmpBaseDir:
            sourceRepo = os.path.join(tmpBaseDir, "repository")
            destinationRepo = os.path.join(tmpBaseDir, "destination_online_repository")

            _write_dummy_file(os.path.join(sourceRepo, "qt.foo.bar1", "meta", "package.xml"))
            _write_dummy_file(os.path.join(sourceRepo, "qt.foo.bar2", "meta", "package.xml"))
            _write_dummy_file(os.path.join(sourceRepo, "Updates.xml"))

            upload_pending_repository_content(self.server, sourceRepo, destinationRepo)
            self.assertListEqual(sorted(os.listdir(sourceRepo)), sorted(os.listdir(destinationRepo)))

    @asyncio_test
    async def test_reset_new_remote_repository(self) -> None:
        with TemporaryDirectory(dir=os.getcwd(), prefix="_repo_tmp_") as tmpBaseDir:
            remoteSourceRepoPath = os.path.join(tmpBaseDir, "repository")
            remoteTargetRepoPath = os.path.join(tmpBaseDir, "destination_online_repository")

            _write_dummy_file(os.path.join(remoteSourceRepoPath, "qt.foo.bar1", "meta", "package.xml"))
            _write_dummy_file(os.path.join(remoteSourceRepoPath, "qt.foo.bar2", "meta", "package.xml"))
            _write_dummy_file(os.path.join(remoteSourceRepoPath, "Updates.xml"))

            reset_new_remote_repository(self.server, remoteSourceRepoPath, remoteTargetRepoPath)
            self.assertTrue(os.path.isfile(os.path.join(remoteTargetRepoPath, "qt.foo.bar1", "meta", "package.xml")))
            self.assertTrue(os.path.isfile(os.path.join(remoteTargetRepoPath, "qt.foo.bar2", "meta", "package.xml")))
            self.assertTrue(os.path.isfile(os.path.join(remoteTargetRepoPath, "Updates.xml")))

            # existing repository should be automatically be moved as backup
            reset_new_remote_repository(self.server, remoteSourceRepoPath, remoteTargetRepoPath)
            self.assertTrue(os.path.exists(remoteTargetRepoPath + "____snapshot_backup"))

    @asyncio_test
    async def test_create_remote_repository_backup(self) -> None:
        with TemporaryDirectory(dir=os.getcwd(), prefix="_repo_tmp_") as tmpBaseDir:
            remoteSourceRepoPath = os.path.join(tmpBaseDir, "repository")

            _write_dummy_file(os.path.join(remoteSourceRepoPath, "qt.foo.bar1", "meta", "package.xml"))
            _write_dummy_file(os.path.join(remoteSourceRepoPath, "qt.foo.bar2", "meta", "package.xml"))
            _write_dummy_file(os.path.join(remoteSourceRepoPath, "Updates.xml"))

            remoteRepoBackupPath = create_remote_repository_backup(self.server, remoteSourceRepoPath)
            self.assertFalse(os.path.exists(remoteSourceRepoPath))
            self.assertListEqual(sorted(["Updates.xml", "qt.foo.bar1", "qt.foo.bar2"]), sorted(os.listdir(remoteRepoBackupPath)))

    @asyncio_test_parallel_data((True, True), (False, False), ("yes", True), ("1", True), ("y", True),
                                ("false", False), ("n", False), ("0", False), ("no", False))
    async def test_string_to_bool(self, value: str, expectedResult: bool) -> None:
        self.assertEqual(string_to_bool(value), expectedResult)

    @asyncio_test
    async def test_build_online_repositories_dryrun(self) -> None:
        sample_config = """
            [task.repository.linux.x86_64.repo1]
            config_file: foobar_config_file
            repo_path: foo/bar/path_1
        """
        config = ConfigParser()
        config.read_string(sample_config)

        # parse all tasks i.e. no filters
        tasks = parse_data(config, task_filters=[])
        await build_online_repositories(tasks=tasks, license="opensource", installerConfigBaseDir="foo", artifactShareBaseUrl="foo",
                                        ifwTools="foo", buildRepositories=False)
        task = tasks.pop()
        self.assertTrue(task.source_online_repository_path.endswith("foo/bar/path_1/online_repository"))

    @asyncio_test
    async def test_ensure_ext_repo_paths(self) -> None:
        with TemporaryDirectory(dir=os.getcwd(), prefix="_repo_tmp_") as tmpBaseDir:
            expectedRepo = os.path.join(tmpBaseDir, "some", "test", "path")
            await ensure_ext_repo_paths(self.server, self.server, expectedRepo)
            self.assertTrue(os.path.isdir(expectedRepo))

    @asyncio_test_parallel_data(
        ("user@server.com:/foo/bar"),
        ("server.com:/foo/bar"),
        ("user@server.com:/"), unpack=False
    )
    async def test_parse_ext_valid(self, ext) -> None:
        parse_ext(ext)

    @asyncio_test_parallel_data(
        ("user@server.com"),
        ("server.com:/foo/bar:"),
        ("user@server.com:some/path"), unpack=False
    )
    async def test_parse_ext_invalid(self, ext) -> None:
        with self.assertRaises(PackagingError):
            parse_ext(ext)

    @asyncio_test_parallel_data(
        ("Error: Repository parameter missing argument"),
        ("Invalid content in ..."),
        ("Repository target directory /foobar/bar/foo already exists."), unpack=False
    )
    async def test_check_invalid_repogen_output(self, repogen_output) -> None:
        with self.assertRaises(PackagingError):
            check_repogen_output(repogen_output)

    @asyncio_test_parallel_data(
        ("Update component a.b.c.d"),
        ("Cannot find new components to update"), unpack=False
    )
    async def test_check_valid_repogen_output(self, repogen_output) -> None:
        # should not throw exception
        check_repogen_output(repogen_output)

    @asyncio_test_parallel_data(
        ([], ["repository"]),
        (["linux,common"], ["repository,linux,common"]),
        (["", "linux,common"], ["repository", "repository,linux,common"])
    )
    async def test_append_to_task_filters(self, task_filters: List[str], exp_result: bool) -> None:
        self.assertEqual(append_to_task_filters(task_filters, "repository"), exp_result)

    @asyncio_test_parallel_data(
        (["task.repository.linux.x64.feature1"], ["task,repository,linux,x64,feature1"]),
        (["task.repository.linux.x64.feature1", "windows.x64,feature2"],
         ["task,repository,linux,x64,feature1", "windows,x64,feature2"]),
        (["offline,linux.x64,feature1"], ["offline,linux,x64,feature1"]),
        (["linux"], ["linux"]),
        ([""], [""])
    )
    async def test_format_task_filters(self, task_filters: List[str], exp_result: bool) -> None:
        print("test")
        self.assertEqual(format_task_filters(task_filters), exp_result)

    @asyncio_test_parallel_data(
        ("qtsdkrepository/windows_x86/desktop/tools_maintenance/log-s3-2020-12-03--10:18:11-xml.t"
         "xt:fatal error: Could not connect to the endpoint URL: 'https://qt-cdn.s3.eu-west-1.ama"
         "zonaws.com/?list-type=2&prefix=qtsdkrepository%2Fwindows_x86%2Fdesktop%2Ftools_maintena"
         "nce%2F&encoding-type=url'qtsdkrepository/", True),
        ("qtsdkrepository/windows_x86/desktop/tools_maintenance/log-s3-2020-12-03--10:18:11-xml.t"
         "xt:fatal error: to the endpoint URL: 'https://qt-cdn.s3.eu-west-1.amazonaws.com/?list-t"
         "ype=2&prefix=qtsdkrepository%2Fwindows_x86%2Fdesktop%2Ftools_maintenance%2F&encoding-ty"
         "pe=url'qtsdkrepository/", False),
        ("", False)
    )
    async def test_has_connection_error(self, output: str, expected_result: bool) -> None:
        self.assertEqual(expected_result, has_connection_error(output))


if __name__ == '__main__':
    unittest.main()
