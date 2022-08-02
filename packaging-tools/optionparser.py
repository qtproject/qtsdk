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
import argparse
import os
import sys
from configparser import ConfigParser
from typing import Dict

from logging_util import init_logger

log = init_logger(__name__, debug_mode=False)


class PackagingOptions:
    """Utility class to read options from configuration file that follows .ini file format."""
    def __init__(self, conf_file: str) -> None:
        if not os.path.isfile(conf_file):
            raise IOError(f"Not a valid file: {conf_file}")
        self.config = ConfigParser(os.environ)
        self.config.optionxform = str  # type: ignore
        self.config.read(conf_file)

    def config_section_map(self, section: str) -> Dict[str, str]:
        dict1 = {}
        options = self.config.options(section)
        for option in options:
            try:
                dict1[option] = self.config.get(section, option)
                if dict1[option] == "-1":
                    log.info("skip: %s", option)
            except Exception:
                log.warning("exception on %s!", option)
                dict1[option] = ""
        return dict1

    def section_exists(self, section: str) -> bool:
        return self.config.has_section(section)

    def option_exists(self, section: str, option: str) -> bool:
        return self.section_exists(section) and self.config.has_option(section, option)

    def config_map(self) -> Dict[str, str]:
        dict1 = {}
        for section in self.config.sections():
            dict1.update(self.config_section_map(section))
        return dict1

    def verbose(self) -> None:
        for section in self.config.sections():
            log.info("[%s]", section)
            options = self.config.options(section)
            for option in options:
                log.info("%s = %s", option, self.config.get(section, option))


def get_pkg_options(conf_file_path: str) -> PackagingOptions:
    return PackagingOptions(conf_file_path)


def main() -> None:
    """Main"""
    parser = argparse.ArgumentParser(prog="Parse packaging related options from config file.")
    parser.add_argument("--conf-file", dest="conf_file", required=True, type=str,
                        help="Absolute path pointing into configuration file which contains all required options for packaging.")
    args = parser.parse_args(sys.argv[1:])
    # Print out all options
    options = get_pkg_options(args.conf_file)
    config_map = options.config_map()
    log.info(config_map)


if __name__ == '__main__':
    main()
