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

from ddt import ddt

from release_task_reader import ReleaseTaskError, get_filter_parts, parse_data
from tests.testhelpers import asyncio_test, asyncio_test_parallel_data


@ddt
class TestReleaseTaskReader(unittest.TestCase):

    @asyncio_test_parallel_data(("linux,x64,common", ["linux", "x64", "common"]),
                                ("linux, x64,  common ", ["linux", "x64", "common"]),
                                ("linux; , x64  common ", ["linux", "x64", "common"]),
                                (": ,,; linux x64   common ", ["linux", "x64", "common"]))
    async def test_get_filter_parts(self, task_filters: str, expected_result: List[str]) -> None:
        self.assertEqual(get_filter_parts(task_filters), expected_result)

    @asyncio_test
    async def test_release_task_reader(self) -> None:
        sample_config = """
            [task.repository.linux.x86_64]
            config_file:  foobar-file-repository
            substitutions: arg1, arg2, arg3
            repo_components_to_update: *
            repo_path: foo/bar/path
            rta_key_list: key1, key2,key3   , key4

            [task.offline.linux.x86_64.foobar]
            config_file:  foobar-file-repository-2
            substitutions: arg1, arg2, arg3
            repo_components_to_update: *
            repo_path: foo/bar/path2
            rta_key_list: key1, key2,key3   , key4

            [task.offline.linux.x86_64]
            config_file:  foobar-file-offline
            substitutions: arg11, arg21, arg31
            rta_key_list: keyA, keyB

            [task.online.linux.x86_64]
            config_file:  foobar-file-online
            substitutions: arg12, arg22, arg32
            rta_key_list: key12, key22

            [foo.online.linux.x86_64]
            config_file:  foobar-file-online
            substitutions: arg13, arg23, arg33
            rta_key_list: key13, key23
        """
        config = ConfigParser()
        config.read_string(sample_config)

        # parse all tasks i.e. no filters
        tasks = parse_data(config, task_filters=[])
        self.assertTrue(len(tasks) == 4, "Did not parse all tasks from sample config")

        # parse only "repository" tasks
        tasks = parse_data(config, task_filters=["repository"])
        self.assertTrue(len(tasks) == 1)
        self.assertEqual(tasks[0].is_repository_task(), True)
        self.assertEqual(tasks[0].is_offline_installer_task(), False)
        self.assertEqual(tasks[0].is_online_installer_task(), False)
        self.assertEqual(tasks[0].get_config_file(), "foobar-file-repository")
        self.assertEqual(tasks[0].get_substitutions(), "arg1, arg2, arg3")
        self.assertEqual(tasks[0].get_installer_string_replacement_list(), ["arg1", "arg2", "arg3"])
        self.assertEqual(tasks[0].get_repo_components_to_update(), "*")
        self.assertEqual(tasks[0].get_repo_path(), "foo/bar/path")
        self.assertEqual(sorted(tasks[0].get_rta_key_list()), sorted(["key1", "key2", "key3", "key4"]))

        # parse only "offline" tasks with multiple filters
        tasks = parse_data(config, task_filters=["offline,linux,x86_64"])
        self.assertTrue(len(tasks) == 2)
        tasks = parse_data(config, task_filters=["offline,linux,x86_64,foobar"])
        self.assertTrue(len(tasks) == 1)

        # parse "offline" tasks with multiple filters and "online" tasks
        tasks = parse_data(config, task_filters=["offline,linux,x86_64", "online,linux,x86_64"])
        self.assertTrue(len(tasks) == 3)

    @asyncio_test
    async def test_release_task_reader_invalid_config(self) -> None:
        sample_config = """
            [task.repository]
            config_file:  foobar-file-repository
            substitutions: arg1, arg2, arg3
            repo_components_to_update: *
            repo_path: foo/bar/path
            rta_key_list: key1, key2
        """
        config = ConfigParser()
        config.read_string(sample_config)
        with self.assertRaises(ReleaseTaskError):
            parse_data(config, task_filters=[])


if __name__ == '__main__':
    unittest.main()
