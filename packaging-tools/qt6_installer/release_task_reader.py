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

import os
import re
import sys
import argparse
from typing import List, Dict
from configparser import ConfigParser, ExtendedInterpolation
from logging_util import init_logger

log = init_logger(__name__, debug_mode=False)


class ReleaseTaskError(Exception):
    pass


class ReleaseTask:

    def __init__(self, name: str, settings: Dict[str, str]):
        if not len(name.split(".")) >= 3:
            raise ReleaseTaskError("The '[{0}]' has too few dot separated elements!".format(name))
        self.name = name
        self.config_file = settings["config_file"]
        self.substitutions = settings.get("substitutions", "")
        self.repo_path = settings.get("repo_path", "")
        self.repo_components_to_update = settings.get("repo_components_to_update", "")
        self.rta_key_list = settings.get("rta_key_list", "")
        tmpList = [x.strip() for x in self.substitutions.split(',')] if self.substitutions else []  # type: List[str]
        self.installer_string_replacement_list = list(filter(None, tmpList))
        self.source_online_repository_path = ""
        self.source_pkg_path = ""

    def add_to_substitutions_list(self, substitutions: List[str]) -> None:
        self.installer_string_replacement_list += substitutions

    def is_repository_task(self) -> bool:
        return self.name.split(".")[1] == "repository"

    def is_offline_installer_task(self) -> bool:
        return self.name.split(".")[1] == "offline"

    def is_online_installer_task(self) -> bool:
        return self.name.split(".")[1] == "online"

    def get_config_file(self) -> str:
        return self.config_file

    def get_substitutions(self) -> str:
        return self.substitutions

    def get_installer_string_replacement_list(self) -> List[str]:
        return self.installer_string_replacement_list

    def get_repo_components_to_update(self) -> str:
        return self.repo_components_to_update

    def get_repo_path(self) -> str:
        return self.repo_path

    def get_rta_key_list(self) -> List[str]:
        tmpList = self.rta_key_list.strip().replace(' ', '').split(",")
        return list(filter(None, tmpList))

    def get_source_online_repository_path(self) -> str:
        # this points to local repository build path
        return self.source_online_repository_path

    def get_source_pkg_path(self) -> str:
        # this points to local repository build path
        return self.source_pkg_path


def parse_substitutions_list(parser, section) -> List[str]:
    try:
        args = parser[section]['substitutions']
        return [x.strip() for x in args.split(',')]
    except KeyError:
        # it's ok, the 'substitutions' is not mandatory
        pass
    return []


def get_filter_parts(section_filters: str) -> List[str]:
    return list(filter(None, re.split("[, ;:]+", section_filters)))


def parse_data(settings, task_filters: List[str]) -> List[ReleaseTask]:
    tasks = []  # type: List[ReleaseTask]
    common_substitution_list = parse_substitutions_list(settings, 'common.substitutions')
    section_filters_list = [get_filter_parts(x) for x in task_filters]

    for section in settings.sections():
        parts = section.split(".")
        if not parts[0].startswith("task"):
            continue
        appendTask = True
        if section_filters_list:
            appendTask = False
            for section_filters in section_filters_list:
                if set(section_filters).issubset(set(parts)):
                    appendTask = True
                    break
        if appendTask:
            log.info("Parsing Task: %s", section)
            releaseTask = ReleaseTask(section, settings[section])
            releaseTask.add_to_substitutions_list(common_substitution_list)
            tasks.append(releaseTask)
        else:
            log.info("Skipping task: [%s] - not included by task filter(s): %s", section, section_filters_list)
    return tasks


def parse_config(configFile: str, task_filters: List[str]) -> List[ReleaseTask]:
    if not os.path.isfile(configFile):
        raise ReleaseTaskError("Not such file: {0}".format(configFile))
    settings = ConfigParser(interpolation=ExtendedInterpolation())
    settings.read(configFile)
    return parse_data(settings, task_filters)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="Script to parse top level release config file")
    parser.add_argument("--config", dest="config", type=str, default=os.getenv("RELEASE_DESCRIPTION_FILE"),
                        help="Path to top level release config file")
    parser.add_argument("--task-filter", dest="task_filters", action='append',
                        help="Task include filters per section name in the --config file to match with " \
                        "the section name, e.g. 'offline', 'repository', ...")
    args = parser.parse_args(sys.argv[1:])

    assert os.path.isfile(args.config), "Not a valid file: {0}".format(args.config)
    parse_config(args.config, args.task_filters)
