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
from configparser import ConfigParser
from typing import List

from ddt import data, ddt, unpack  # type: ignore

from release_task_reader import (
    QBSPReleaseTask,
    ReleaseTaskError,
    TaskType,
    get_filter_parts,
    parse_data,
)
from tests.testhelpers import asyncio_test, asyncio_test_parallel_data


@ddt
class TestReleaseTaskReader(unittest.TestCase):
    @asyncio_test_parallel_data(  # type: ignore
        ("linux,x64,common", ["linux", "x64", "common"]),
        ("linux, x64,  common ", ["linux", "x64", "common"]),
        ("linux; , x64  common ", ["linux", "x64", "common"]),
        (": ,,; linux x64   common ", ["linux", "x64", "common"]),
    )
    async def test_get_filter_parts(self, task_filters: str, expected_result: List[str]) -> None:
        self.assertEqual(get_filter_parts(task_filters), expected_result)

    @data(  # type: ignore
        ("""
            [task.ifw.repository.linux.x86_64]
            config_file:  foobar-file-repository
            substitutions: arg1, arg2, arg3
            repo_path: foo/bar/path
            rta_key_list: key1
        """, ["ifw,repository,linux"], TaskType.IFW_TASK_TYPE, True),
        ("""
            [task.ifw.repository.linux2.x64.common]
            config_file:  foobar-file-repository
            repo_path: foo/bar/path

            [task.ifw.repository.linux.exclude.common]
            config_file:  foobar-file-repository
            repo_path: foo/bar/path
        """, ["common, x64"], TaskType.IFW_TASK_TYPE, True),
        ("""
            [task.ifw.repository.linux.x64.no_repo_path]
            substitutions: arg1, arg2, arg3
        """, ["no_repo_path"], TaskType.IFW_TASK_TYPE, False),
        ("""
            [task.ifw.repository.linux.x64.no_config_file]
            repo_path: foo/bar/path
        """, ["no_config_file"], TaskType.IFW_TASK_TYPE, False),
        ("""
            [task.deb.repository.linux.x64]
            repo_path: foo/bar/path
        """, ["deb,linux"], TaskType.DEB_TASK_TYPE, True),
        ("""
            [task.deb.repository.linux.x64]
        """, ["deb"], TaskType.DEB_TASK_TYPE, False),
        ("""
            [task.ifw.offline.linux.x64.no_config_file]
        """, ["ifw,offline"], TaskType.IFW_TASK_TYPE, False),
        ("""
            [task.ifw.offline.linux.x64]
            config_file:  foobar-file-repository
        """, ["ifw,offline"], TaskType.IFW_TASK_TYPE, True)
    )
    @unpack  # type: ignore
    def test_release_task_validity(
        self,
        sample_config: str,
        filters: List[str],
        task_type: TaskType,
        is_valid: bool,
    ) -> None:
        config = ConfigParser()
        config.read_string(sample_config)
        if is_valid:
            self.assertIsNotNone(parse_data(config, task_types=[task_type], task_filters=filters))
        else:
            with self.assertRaises(ReleaseTaskError):
                parse_data(config, task_types=[task_type], task_filters=filters)

    @data(  # type: ignore
        ("""
            [task.ifw.repository.linux.x86_64]
            config_file:  foobar-file-repository
            substitutions: arg1, arg2, arg3
            repo_path: foo/bar/path
            rta_key_list: key1, key2,key3   , key4

            [task.ifw.offline.linux.x86_64.foobar]
            config_file:  foobar-file-repository-2
            substitutions: arg1, arg2, arg3
            repo_path: foo/bar/path2
            rta_key_list: key1, key2,key3   , key4

            [task.ifw.offline.linux.x86_64]
            config_file:  foobar-file-offline
            substitutions: arg11, arg21, arg31
            repo_path: foo/bar/path
            rta_key_list: keyA, keyB

            [task.ifw.online.linux.x86_64]
            config_file:  foobar-file-online
            substitutions: arg12, arg22, arg32
            repo_path: foo/bar/path
            rta_key_list: key12, key22

            [foo.ifw.online.linux.x86_64]
            config_file:  foobar-file-online
            substitutions: arg13, arg23, arg33
            repo_path: foo/bar/path
            rta_key_list: key13, key23
        """,)
    )
    @unpack  # type: ignore
    def test_release_task_reader_ifw(self, sample_config: str) -> None:
        config = ConfigParser()
        config.read_string(sample_config)
        # parse all tasks i.e. no filters
        tasks = parse_data(config, task_types=[TaskType.IFW_TASK_TYPE], task_filters=[])
        self.assertTrue(
            len(tasks[TaskType.IFW_TASK_TYPE]) == 4, "Did not parse all tasks from sample config"
        )
        # parse only "repository" tasks
        tasks = parse_data(
            config, task_types=[TaskType.IFW_TASK_TYPE], task_filters=["repository"]
        )
        self.assertTrue(len(tasks[TaskType.IFW_TASK_TYPE]) == 1)
        self.assertEqual(
            tasks[TaskType.IFW_TASK_TYPE][0].config_file, "foobar-file-repository"
        )
        self.assertEqual(
            tasks[TaskType.IFW_TASK_TYPE][0].substitutions, ["arg1", "arg2", "arg3"]
        )
        self.assertEqual(
            tasks[TaskType.IFW_TASK_TYPE][0].rta_key_list, ["key1", "key2", "key3", "key4"]
        )
        self.assertEqual(tasks[TaskType.IFW_TASK_TYPE][0].repo_path, "foo/bar/path")
        self.assertEqual(sorted(tasks[TaskType.IFW_TASK_TYPE][0].rta_key_list), sorted(["key1", "key2", "key3", "key4"]))

        # parse only "offline" tasks with multiple filters
        tasks = parse_data(
            config,
            task_types=[TaskType.IFW_TASK_TYPE],
            task_filters=["offline,linux,x86_64"],
        )
        self.assertTrue(len(tasks[TaskType.IFW_TASK_TYPE]) == 2)
        tasks = parse_data(
            config,
            task_types=[TaskType.IFW_TASK_TYPE],
            task_filters=["offline,linux,x86_64,foobar"],
        )
        self.assertTrue(len(tasks[TaskType.IFW_TASK_TYPE]) == 1)

        # parse "offline" tasks with multiple filters and "online" tasks
        tasks = parse_data(
            config,
            task_types=[TaskType.IFW_TASK_TYPE],
            task_filters=["offline,linux,x86_64", "online,linux,x86_64"],
        )
        self.assertTrue(len(tasks[TaskType.IFW_TASK_TYPE]) == 3)

    @asyncio_test
    async def test_release_task_reader_deb(self) -> None:
        sample_config = """
            [task.deb.repository.linux.amd64]
            repo_path: test_repo/amd64
            distribution:  foobar-file-repository-amd64
            component: main
            architectures: amd64
            content_sources: http://foo.com/content1, http://foo.com/content2
            substitutions: foo=bar, aaa=bbb
            rta_key_list: key1, key2

            [task.deb.repository.linux.arm64]
            repo_path: test_repo/arm64
            distribution:  foobar-file-repository-arm64
            component: main
            architectures: arm64
            content_sources: http://foo.com/content3, http://foo.com/content4
            substitutions: foo=bar, aaa=bbb
            rta_key_list: key3, key4
        """
        config = ConfigParser()
        config.read_string(sample_config)

        # parse all tasks i.e. no filters
        tasks = parse_data(config, task_types=[TaskType.DEB_TASK_TYPE], task_filters=[])
        self.assertTrue(len(tasks[TaskType.DEB_TASK_TYPE]) == 2, "Did not parse all tasks from sample config")

        # parse only "repository" tasks
        tasks = parse_data(config, task_types=[TaskType.DEB_TASK_TYPE], task_filters=["amd64"])
        self.assertTrue(len(tasks[TaskType.DEB_TASK_TYPE]) == 1)
        self.assertEqual(tasks[TaskType.DEB_TASK_TYPE][0].substitutions, ["foo=bar", "aaa=bbb"])
        self.assertEqual(tasks[TaskType.DEB_TASK_TYPE][0].repo_path, "test_repo/amd64")
        self.assertEqual(
            tasks[TaskType.DEB_TASK_TYPE][0].distribution,  # type: ignore
            "barbar-file-repository-amd64"
        )
        self.assertEqual(tasks[TaskType.DEB_TASK_TYPE][0].component, "main")  # type: ignore
        self.assertEqual(tasks[TaskType.DEB_TASK_TYPE][0].architectures, ["amd64"])  # type: ignore
        self.assertEqual(
            tasks[TaskType.DEB_TASK_TYPE][0].content_sources,  # type: ignore
            ["http://bar.com/content1", "http://bar.com/content2"]
        )
        self.assertEqual(
            sorted(tasks[TaskType.DEB_TASK_TYPE][0].rta_key_list), sorted(["key1", "key2"])
        )

    @asyncio_test
    async def test_release_task_reader_qbsp(self) -> None:
        sample_config = """
            [task.qbsp.repository.linux.foo]
            qbsp_file: https://foo.com/path1/foo.qbsp
            repo_path: test_repo/temp1
            rta_key_list: key1, key2

            [task.qbsp.repository.linux.bar]
            qbsp_file: https://foo.com/path2/bar.qbsp
            repo_path: test_repo/temp2
            rta_key_list: key3, key4
        """
        config = ConfigParser()
        config.read_string(sample_config)

        # parse all tasks i.e. no filters
        tasks = parse_data(config, task_types=[TaskType.QBSP_TASK_TYPE], task_filters=[])
        self.assertTrue(len(tasks[TaskType.QBSP_TASK_TYPE]) == 2, "Did not parse all tasks from sample config")

        # parse only "foo" tasks
        tasks = parse_data(config, task_types=[TaskType.QBSP_TASK_TYPE], task_filters=["foo"])
        self.assertTrue(len(tasks[TaskType.QBSP_TASK_TYPE]) == 1)
        task = tasks[TaskType.QBSP_TASK_TYPE].pop()
        assert isinstance(task, QBSPReleaseTask)
        self.assertEqual(task.qbsp_file, "https://foo.com/path1/foo.qbsp")
        self.assertEqual(task.repo_path, "test_repo/temp1")
        self.assertEqual(sorted(task.rta_key_list), sorted(["key1", "key2"]))

    @asyncio_test
    async def test_release_task_reader_invalid_config(self) -> None:
        sample_config = """
            [task.ifw.repository]
            config_file:  foobar-file-repository
            substitutions: arg1, arg2, arg3
            repo_path: foo/bar/path
            rta_key_list: key1, key2
        """
        config = ConfigParser()
        config.read_string(sample_config)
        with self.assertRaises(ReleaseTaskError):
            parse_data(config, task_types=[TaskType.IFW_TASK_TYPE], task_filters=[])


if __name__ == '__main__':
    unittest.main()
