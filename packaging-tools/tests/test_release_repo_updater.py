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

import os
import unittest
from configparser import ConfigParser
from pathlib import Path
from shutil import rmtree
from typing import List, cast

from ddt import ddt  # type: ignore
from temppathlib import TemporaryDirectory

from installer_utils import PackagingError, ch_dir
from read_remote_config import get_pkg_value
from release_repo_updater import (
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
from release_task_reader import IFWReleaseTask, TaskType, append_to_task_filters, parse_data
from tests.testhelpers import (
    asyncio_test,
    asyncio_test_parallel_data,
    is_internal_file_server_reachable,
)


def _write_dummy_file(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w+', encoding="utf-8") as handle:
        handle.write("\n")


def _write_package_xml(path: str, version: str, release_date: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w+', encoding="utf-8") as handle:
        handle.write("<?xml version=\"1.0\"?>\n")
        handle.write("<Package>\n")
        handle.write("  <Name>qt.foo.bar1</Name>\n")
        handle.write("  <DisplayName>Test</DisplayName>\n")
        handle.write("  <Description>Test</Description>\n")
        handle.write(f"  <Version>{version}</Version>\n")
        handle.write(f"  <ReleaseDate>{release_date}</ReleaseDate>\n")
        handle.write("</Package>\n")


def _write_updates_xml(path: str, version: str, release_date: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w+', encoding="utf-8") as handle:
        handle.write("<Updates>\n")
        handle.write("  <ApplicationName>{AnyApplication}</ApplicationName>\n")
        handle.write("  <ApplicationVersion>1.0.0</ApplicationVersion>\n")
        handle.write("  <Checksum>false</Checksum>\n")
        handle.write("  <PackageUpdate>\n")
        handle.write("    <Name>qt.foo.bar1</Name>\n")
        handle.write("    <DisplayName>Foo bar</DisplayName>\n")
        handle.write("    <Description>Foo and bar</Description>\n")
        handle.write(f"    <Version>{version}</Version>\n")
        handle.write(f"    <ReleaseDate>{release_date}</ReleaseDate>\n")
        handle.write("    <DownloadableArchives/>\n")
        handle.write("    <UpdateFile CompressedSize=\"0\" OS=\"Any\" UncompressedSize=\"0\"/>\n")
        handle.write("    <SHA1>c1559cbb0f0983909f7229dc79dfdf7eab46cd52</SHA1>\n")
        handle.write("  </PackageUpdate>\n")
        handle.write("</Updates>\n")


async def _get_repogen() -> str:
    pkgsrv = get_pkg_value("PACKAGE_STORAGE_SERVER_PATH_HTTP")
    ifw_tools = (
        f"{pkgsrv}/archive/ifw/enterprise/unifiedqt/4.3.0/tqtc-installer-framework-Linux-RHEL_7_6-"
        "GCC-Linux-RHEL_7_6-X86_64.7z"
    )
    server = "127.0.0.1"
    with TemporaryDirectory() as temp_dir:
        with ch_dir(str(temp_dir.path)):
            return await upload_ifw_to_remote(ifw_tools, server)


@ddt
class TestReleaseRepoUpdater(unittest.TestCase):
    server = None  # type: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = "127.0.0.1"

    @asyncio_test
    async def test_remote_file_exists(self) -> None:
        self.assertTrue(remote_file_exists(self.server, os.path.abspath(__file__)))
        self.assertFalse(remote_file_exists(self.server, "/some/bogus/directory/foo.txt"))

    @unittest.skipUnless(is_internal_file_server_reachable(), "Skipping because file server is not accessible")
    @asyncio_test
    async def test_upload_ifw_to_remote(self) -> None:
        repogen = ""
        try:
            repogen = await _get_repogen()
        finally:
            repogen_path = Path.home() / repogen
            self.assertTrue(repogen_path.is_file())
            rmtree(repogen_path.parent)

    @asyncio_test
    async def test_upload_pending_repository_content(self) -> None:
        with TemporaryDirectory(prefix="_repo_tmp_") as tmp_dir:
            tmp_base_dir = tmp_dir.path
            source_repo = tmp_base_dir / "repository"
            destination_repo = tmp_base_dir / "destination_online_repository"

            _write_dummy_file(str(source_repo / "qt.foo.bar1" / "meta" / "package.xml"))
            _write_dummy_file(str(source_repo / "qt.foo.bar2" / "meta" / "package.xml"))
            _write_dummy_file(str(source_repo / "Updates.xml"))

            upload_pending_repository_content(self.server, str(source_repo), str(destination_repo))
            self.assertListEqual(
                sorted([x.relative_to(source_repo) for x in source_repo.iterdir()]),
                sorted([x.relative_to(destination_repo) for x in destination_repo.iterdir()])
            )

    @asyncio_test
    async def test_reset_new_remote_repository(self) -> None:
        with TemporaryDirectory(prefix="_repo_tmp_") as tmp_dir:
            tmp_base_dir = tmp_dir.path
            remote_source_repo_path = tmp_base_dir / "repository"
            remote_target_repo_path = tmp_base_dir / "destination_online_repository"

            _write_dummy_file(str(remote_source_repo_path / "qt.foo.bar1" / "meta" / "package.xml"))
            _write_dummy_file(str(remote_source_repo_path / "qt.foo.bar2" / "meta" / "package.xml"))
            _write_dummy_file(str(remote_source_repo_path / "Updates.xml"))

            reset_new_remote_repository(self.server, str(remote_source_repo_path), str(remote_target_repo_path))
            self.assertTrue((remote_target_repo_path / "qt.foo.bar1" / "meta" / "package.xml").is_file())
            self.assertTrue((remote_target_repo_path / "qt.foo.bar2" / "meta" / "package.xml").is_file())
            self.assertTrue((remote_target_repo_path / "Updates.xml").is_file())

            # existing repository should be automatically be moved as backup
            reset_new_remote_repository(self.server, str(remote_source_repo_path), str(remote_target_repo_path))
            backup_name = remote_target_repo_path.name + "____snapshot_backup"
            self.assertTrue((remote_target_repo_path.with_name(backup_name)).exists())

    @asyncio_test
    async def test_create_remote_repository_backup(self) -> None:
        with TemporaryDirectory(prefix="_repo_tmp_") as tmp_dir:
            tmp_base_dir = tmp_dir.path
            remote_source_repo_path = tmp_base_dir / "repository"

            _write_dummy_file(str(remote_source_repo_path / "qt.foo.bar1" / "meta" / "package.xml"))
            _write_dummy_file(str(remote_source_repo_path / "qt.foo.bar2" / "meta" / "package.xml"))
            _write_dummy_file(str(remote_source_repo_path / "Updates.xml"))

            remote_repo_backup_path = Path(
                create_remote_repository_backup(
                    self.server, str(remote_source_repo_path)
                )
            )
            self.assertFalse(remote_source_repo_path.exists())
            self.assertListEqual(
                sorted(["Updates.xml", "qt.foo.bar1", "qt.foo.bar2"]),
                sorted([x.name for x in remote_repo_backup_path.iterdir()])
            )

    @asyncio_test_parallel_data(  # type: ignore
        (True, True),
        (False, False),
        ("yes", True),
        ("1", True),
        ("y", True),
        ("false", False),
        ("n", False),
        ("0", False),
        ("no", False),
    )
    async def test_string_to_bool(self, value: str, expected_result: bool) -> None:
        self.assertEqual(string_to_bool(value), expected_result)

    @asyncio_test
    async def test_build_online_repositories_dryrun(self) -> None:
        sample_config = """
            [task.ifw.repository.linux.x86_64.repo1]
            config_file: foobar_config_file
            repo_path: foo/bar/path_1
        """
        config = ConfigParser()
        config.read_string(sample_config)

        # parse all tasks i.e. no filters
        tasks = parse_data(config, task_types=[TaskType.IFW_TASK_TYPE], task_filters=[])
        await build_online_repositories(
            tasks=cast(List[IFWReleaseTask], tasks[TaskType.IFW_TASK_TYPE]),
            license_="opensource",
            installer_config_base_dir="foo",
            artifact_share_base_url="foo",
            ifw_tools="foo",
            build_repositories=False,
        )
        task = cast(IFWReleaseTask, tasks[TaskType.IFW_TASK_TYPE].pop())
        self.assertTrue(task.source_online_repository_path.endswith("foo/bar/path_1/online_repository"))

    @asyncio_test
    async def test_ensure_ext_repo_paths(self) -> None:
        with TemporaryDirectory(prefix="_repo_tmp_") as tmp_dir:
            expected_repo = tmp_dir.path / "some" / "test" / "path"
            await ensure_ext_repo_paths(self.server, self.server, str(expected_repo))
            self.assertTrue(expected_repo.is_dir())

    @asyncio_test_parallel_data(  # type: ignore
        ("user@server.com:/foo/bar"),
        ("server.com:/foo/bar"),
        ("user@server.com:/"), unpack=False
    )
    async def test_parse_ext_valid(self, ext: str) -> None:
        parse_ext(ext)

    @asyncio_test_parallel_data(  # type: ignore
        ("user@server.com"),
        ("server.com:/foo/bar:"),
        ("user@server.com:some/path"), unpack=False
    )
    async def test_parse_ext_invalid(self, ext: str) -> None:
        with self.assertRaises(PackagingError):
            parse_ext(ext)

    @asyncio_test_parallel_data(  # type: ignore
        ("Error: Repository parameter missing argument"),
        ("Invalid content in ..."),
        ("Repository target directory /foobar/bar/foo already exists."), unpack=False
    )
    async def test_check_invalid_repogen_output(self, repogen_output: str) -> None:
        with self.assertRaises(PackagingError):
            check_repogen_output(repogen_output)

    @asyncio_test_parallel_data(  # type: ignore
        ("Update component a.b.c.d"),
        ("Cannot find new components to update"), unpack=False
    )
    async def test_check_valid_repogen_output(self, repogen_output: str) -> None:
        # should not throw exception
        check_repogen_output(repogen_output)

    @asyncio_test_parallel_data(  # type: ignore
        ([], ["repository"]),
        (["linux,common"], ["repository,linux,common"]),
        (["", "linux,common"], ["repository", "repository,linux,common"])
    )
    async def test_append_to_task_filters(self, task_filters: List[str], exp_result: bool) -> None:
        self.assertEqual(append_to_task_filters(task_filters, "repository"), exp_result)

    @asyncio_test_parallel_data(  # type: ignore
        (["task.ifw.repository.linux.x64.feature1"], ["task,ifw,repository,linux,x64,feature1"]),
        (["task.ifw.repository.linux.x64.feature1", "windows.x64,feature2"],
         ["task,ifw,repository,linux,x64,feature1", "windows,x64,feature2"]),
        (["offline,linux.x64,feature1"], ["offline,linux,x64,feature1"]),
        (["linux"], ["linux"]),
        ([""], [""])
    )
    async def test_format_task_filters(self, task_filters: List[str], exp_result: bool) -> None:
        self.assertEqual(format_task_filters(task_filters), exp_result)

    @asyncio_test_parallel_data(  # type: ignore
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
