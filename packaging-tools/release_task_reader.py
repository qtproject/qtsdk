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

import argparse
import os
import re
import sys
from abc import ABC, abstractmethod
from configparser import ConfigParser, ExtendedInterpolation, SectionProxy
from enum import Enum
from typing import Any, Dict, List, Type, Union

from installer_utils import PackagingError
from logging_util import init_logger

log = init_logger(__name__, debug_mode=False)


class ReleaseTaskError(Exception):
    pass


class TaskType(Enum):
    IFW_TASK_TYPE = "ifw"
    QBSP_TASK_TYPE = "qbsp"
    DEB_TASK_TYPE = "deb"

    @classmethod
    def from_value(cls, value: str) -> 'TaskType':
        _values = {
            TaskType.IFW_TASK_TYPE.value: TaskType.IFW_TASK_TYPE,
            TaskType.QBSP_TASK_TYPE.value: TaskType.QBSP_TASK_TYPE,
            TaskType.DEB_TASK_TYPE.value: TaskType.DEB_TASK_TYPE,
        }
        return _values[value]


class ReleaseTask(ABC):
    """Abstraction for attributes for online repo/offline installer build jobs."""

    def __init__(self, name: str, settings: SectionProxy, common_substitutions: str):
        self._name = name
        self._settings = settings
        self._substitutions = self._parse_substitutions(common_substitutions)
        self._substitutions += self._parse_substitutions(self._settings.get("substitutions", ""))
        self._subst_map = dict(i.split("=", maxsplit=1) for i in self._substitutions if "=" in i)
        self._subst_pattern = re.compile("|".join(self._subst_map.keys()))

    @property
    def name(self) -> str:
        return self._name

    @property
    def config_file(self) -> str:
        return self._get("config_file")

    @property
    def repo_path(self) -> str:
        return self._get("repo_path")

    @property
    def rta_key_list(self) -> List[str]:
        return self._parse_key_list(self._get("rta_key_list"))

    @property
    def substitutions(self) -> List[str]:
        return self._substitutions

    def _parse_substitutions(self, substitutions: str) -> List[str]:
        return list(filter(None, [x.strip() for x in substitutions.split(',')]))

    def _parse_key_list(self, keys: str) -> List[str]:
        return list(filter(None, keys.strip().replace(' ', '').split(",")))

    def _multireplace(self, text: str) -> str:
        """Replace all substitutions in the given 'text'.

        Args:
            text: The string for which to run the substitutions.

        Returns:
            The converted text if there were matches for the substitutions.
        """
        if not self._subst_map:
            return text
        return self._subst_pattern.sub(lambda m: self._subst_map[re.escape(m.group(0))], text)

    def _get(self, key: str) -> str:
        return self._multireplace(self._settings.get(key, ""))

    def _key_exists(self, key: str) -> bool:
        return self._settings.get(key) is not None

    @abstractmethod
    def validate(self) -> None:
        pass


class DebReleaseTask(ReleaseTask):
    """Attributes specific to Debian repository build jobs."""

    @property
    def distribution(self) -> str:
        return self._get("distribution")

    @property
    def component(self) -> str:
        return self._get("component")

    @property
    def architectures(self) -> List[str]:
        return self._parse_key_list(self._get("architectures"))

    @property
    def snapshot_name(self) -> str:
        return self._multireplace(self.repo_path) + "_snapshot"

    @property
    def content_sources(self) -> List[str]:
        return self._parse_key_list(self._get("content_sources"))

    @property
    def endpoint_type(self) -> str:
        return self._get("endpoint_type")

    @property
    def endpoint_name(self) -> str:
        return self._get("endpoint_name")

    def validate(self) -> None:
        for item in ["repo_path"]:
            if not self._key_exists(item):
                raise ReleaseTaskError(f"Value invalid or missing: {item}")


class IFWBaseReleaseTask(ReleaseTask):

    def __init__(self, name: str, settings: SectionProxy, common_substitutions: str):
        super().__init__(name, settings, common_substitutions)
        self._source_online_repository_path: str = ""

    @property
    def source_online_repository_path(self) -> str:
        if not self._source_online_repository_path:
            raise PackagingError("Something is wrong, 'source_online_repository_path' isn't set!")
        return self._source_online_repository_path

    @source_online_repository_path.setter
    def source_online_repository_path(self, value: str) -> None:
        self._source_online_repository_path = value


class QBSPReleaseTask(IFWBaseReleaseTask):
    """Attributes specific to create IFW online repository from QBSP file."""

    @property
    def qbsp_file(self) -> str:
        return self._get("qbsp_file")

    def validate(self) -> None:
        validate_list = ["qbsp_file"]
        for item in validate_list:
            if not self._key_exists(item):
                raise ReleaseTaskError(f"Value invalid or missing: {item}")


class IFWReleaseTask(IFWBaseReleaseTask):
    """Attributes specific to IFW online repository build jobs."""

    @property
    def installer_name(self) -> str:
        return self._get("installer_name")

    @property
    def project_name(self) -> str:
        return self._get("project_name")

    @property
    def version(self) -> str:
        return self._get("version")

    @property
    def prerelease_version(self) -> str:
        return self._get("prerelease_version")

    def validate(self) -> None:
        validate_list = ["config_file", "repo_path"]
        if "ifw.offline" in self.name:
            validate_list.remove("repo_path")
        for item in validate_list:
            if not self._key_exists(item):
                raise ReleaseTaskError(f"Value invalid or missing: {item}")


class ReleaseTaskFactory:
    """A factory to create a specific ReleaseTask object based on the given configuration data."""

    task_types: Dict[str, Type[ReleaseTask]] = {
        TaskType.IFW_TASK_TYPE.value: IFWReleaseTask,
        TaskType.QBSP_TASK_TYPE.value: QBSPReleaseTask,
        TaskType.DEB_TASK_TYPE.value: DebReleaseTask,
    }

    @classmethod
    def task_from_spec(
        cls,
        task_spec: str,
        requested_task_type: TaskType,
        *args: Any,
        **kwargs: Any,
    ) -> Union[None, IFWReleaseTask, QBSPReleaseTask, DebReleaseTask]:
        """Instantiate a specific ReleaseTask object based on the given configuration.

        Args:
            task_spec: The task specifier i.e. the section name in the .ini file.
            requested_task_type: The type of the ReleaseTask requested. If the 'task_spec' does
                                 not match with the requested
            *args: positional arguments passed to the constructor of the instantiated ReleaseTask
                   object.
            **kwargs: keyword arguments passed to the constructor of the instantiated ReleaseTask
                      object.
        Returns:
            IFWReleaseTask: if 'requested_task_type' was of type TaskType.IFW_TASK_TYPE and the
                            'task_spec' contained matching configuration.
            QBSPReleaseTask: if 'requested_task_type' was of type TaskType.QBSP_TASK_TYPE and the
                            'task_spec' contained matching configuration.
            DebReleaseTask: if 'requested_task_type' was of type TaskType.DEB_TASK_TYPE and the
                            'task_spec' contained matching configuration.
            None: if 'requested_task_type' could not be parsed from the 'task_spec'.
        Raises:
            ReleaseTaskError: if 'task_spec' is unsuitable for ReleaseTask constructing.
        """
        try:
            parsed_type = cls.check_type(task_spec)
            if parsed_type == requested_task_type.value:
                task = cls.task_types[parsed_type](*args, **kwargs)
                task.validate()
                return task  # type: ignore
            return None
        except KeyError as kerr:
            raise ReleaseTaskError(f"Unsupported task type in: {task_spec}") from kerr

    @classmethod
    def check_type(cls, spec: str) -> str:
        parts = spec.split(".")
        if not len(parts) >= 4:
            raise ReleaseTaskError(f"'[{spec}]' should have at least 4 dot separated elements!")
        if not parts[0] == "task":
            raise PackagingError(f"'[{spec}]' should start with 'task.'")
        if not parts[1] in cls.task_types:
            raise PackagingError(f"Invalid: '[{spec}]'. Supported types: {cls.task_types.keys()}")
        return parts[1]


def get_filter_parts(section_filters: str) -> List[str]:
    return list(filter(None, re.split("[, ;:]+", section_filters)))


def append_to_task_filters(task_filters: List[str], task_filter: str) -> List[str]:
    return (
        [task_filter + "," + x if x else task_filter for x in task_filters]
        if task_filters
        else [task_filter]
    )


def parse_data(
    settings: ConfigParser,
    task_type: TaskType,
    task_filters: List[str],
) -> List[Union[IFWReleaseTask, QBSPReleaseTask, DebReleaseTask]]:
    tasks: List[Union[IFWReleaseTask, QBSPReleaseTask, DebReleaseTask]] = []
    sec_filters_list = [get_filter_parts(x) for x in task_filters]
    common_substs = settings.get("common.substitutions", "substitutions", fallback="")

    for section in settings.sections():
        parts = section.split(".")
        if not parts[0].startswith("task"):
            continue
        append_task = True
        if sec_filters_list:
            append_task = False
            for section_filters in sec_filters_list:
                if set(section_filters).issubset(set(parts)):
                    append_task = True
                    break
        if append_task:
            log.info("Parsing Task: %s", section)
            task = ReleaseTaskFactory.task_from_spec(task_spec=section,
                                                     requested_task_type=task_type,
                                                     name=section,
                                                     settings=settings[section],
                                                     common_substitutions=common_substs)
            if task is not None:
                tasks.append(task)
        else:
            log.info("Skipping task: [%s] - excluded by filter(s): %s", section, sec_filters_list)
    return tasks


def parse_config(
    config_file: str,
    task_type: TaskType,
    task_filters: List[str],
) -> List[Union[IFWReleaseTask, QBSPReleaseTask, DebReleaseTask]]:
    if not os.path.isfile(config_file):
        raise ReleaseTaskError(f"Not such file: {config_file}")
    settings = ConfigParser(interpolation=ExtendedInterpolation())
    settings.read(config_file)
    return parse_data(settings, task_type, task_filters)


def main() -> None:
    """Main"""
    parser = argparse.ArgumentParser(prog="Script to parse top level release config file")
    parser.add_argument("--config", dest="config", type=str, default=os.getenv("RELEASE_DESCRIPTION_FILE"),
                        help="Path to top level release config file")
    parser.add_argument("--task-filter", dest="task_filters", action='append',
                        help="Task include filters per section name in the --config file to match with "
                        "the section name, e.g. 'offline', 'repository', ...")
    parser.add_argument("--task-type", dest="task_type", choices=[e.value for e in TaskType],
                        help=f"Define the task type: {[e.value for e in TaskType]}")
    args = parser.parse_args(sys.argv[1:])

    assert os.path.isfile(args.config), f"Not a valid file: {args.config}"
    parse_config(args.config, TaskType.from_value(args.task_type), args.task_filters)


if __name__ == "__main__":
    main()
