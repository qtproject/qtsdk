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

import unittest
from configparser import ConfigParser
from typing import List

from ddt import ddt  # type: ignore

from release_task_reader import ReleaseTaskError, TaskType, get_filter_parts, parse_data
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

    @asyncio_test
    async def test_release_task_reader_ifw(self) -> None:
        sample_config = """
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
            rta_key_list: keyA, keyB

            [task.ifw.online.linux.x86_64]
            config_file:  foobar-file-online
            substitutions: arg12, arg22, arg32
            rta_key_list: key12, key22

            [foo.ifw.online.linux.x86_64]
            config_file:  foobar-file-online
            substitutions: arg13, arg23, arg33
            rta_key_list: key13, key23
        """
        config = ConfigParser()
        config.read_string(sample_config)

        # parse all tasks i.e. no filters
        tasks = parse_data(config, task_type=TaskType.IFW_TASK_TYPE, task_filters=[])
        self.assertTrue(len(tasks) == 4, "Did not parse all tasks from sample config")

        # parse only "repository" tasks
        tasks = parse_data(config, task_type=TaskType.IFW_TASK_TYPE, task_filters=["repository"])
        self.assertTrue(len(tasks) == 1)
        self.assertEqual(tasks[0].config_file, "foobar-file-repository")
        self.assertEqual(tasks[0].substitutions, ["arg1", "arg2", "arg3"])
        self.assertEqual(tasks[0].rta_key_list, ["key1", "key2", "key3", "key4"])
        self.assertEqual(tasks[0].repo_path, "foo/bar/path")
        self.assertEqual(sorted(tasks[0].rta_key_list), sorted(["key1", "key2", "key3", "key4"]))

        # parse only "offline" tasks with multiple filters
        tasks = parse_data(
            config,
            task_type=TaskType.IFW_TASK_TYPE,
            task_filters=["offline,linux,x86_64"],
        )
        self.assertTrue(len(tasks) == 2)
        tasks = parse_data(
            config,
            task_type=TaskType.IFW_TASK_TYPE,
            task_filters=["offline,linux,x86_64,foobar"],
        )
        self.assertTrue(len(tasks) == 1)

        # parse "offline" tasks with multiple filters and "online" tasks
        tasks = parse_data(
            config,
            task_type=TaskType.IFW_TASK_TYPE,
            task_filters=["offline,linux,x86_64", "online,linux,x86_64"],
        )
        self.assertTrue(len(tasks) == 3)

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
        tasks = parse_data(config, task_type=TaskType.DEB_TASK_TYPE, task_filters=[])
        self.assertTrue(len(tasks) == 2, "Did not parse all tasks from sample config")

        # parse only "repository" tasks
        tasks = parse_data(config, task_type=TaskType.DEB_TASK_TYPE, task_filters=["amd64"])
        self.assertTrue(len(tasks) == 1)
        self.assertEqual(tasks[0].substitutions, ["foo=bar", "aaa=bbb"])
        self.assertEqual(tasks[0].repo_path, "test_repo/amd64")
        self.assertEqual(tasks[0].distribution, "barbar-file-repository-amd64")  # type: ignore
        self.assertEqual(tasks[0].component, "main")  # type: ignore
        self.assertEqual(tasks[0].architectures, ["amd64"])  # type: ignore
        self.assertEqual(tasks[0].content_sources, ["http://bar.com/content1",  # type: ignore
                                                    "http://bar.com/content2"])
        self.assertEqual(sorted(tasks[0].rta_key_list), sorted(["key1", "key2"]))

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
            parse_data(config, task_type=TaskType.IFW_TASK_TYPE, task_filters=[])


if __name__ == '__main__':
    unittest.main()
