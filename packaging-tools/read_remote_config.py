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
from io import StringIO
from typing import Any, Optional
from urllib.request import urlopen

from logging_util import init_logger

log = init_logger(__name__, debug_mode=False)


class RemotePkgConfigError(Exception):
    pass


def read_packaging_keys_config_url(url: str) -> Any:
    return urlopen(url).read().decode('utf-8').strip()


def parse_packaging_keys_config(config: str) -> ConfigParser:
    buf = StringIO(config)
    settings = ConfigParser()

    settings.read_file(buf)
    return settings


def get_pkg_value(
    key: str,
    section: str = "packaging",
    url: Optional[str] = os.getenv("PACKAGING_KEYS_CONFIG_URL"),
) -> str:
    if getattr(get_pkg_value, 'pkg_remote_settings', None) is None:
        if not url:
            raise RemotePkgConfigError("Remote config URL not specified")
        config = read_packaging_keys_config_url(url)
        get_pkg_value.pkg_remote_settings = parse_packaging_keys_config(config)  # type: ignore
    return get_pkg_value.pkg_remote_settings.get(section, key)  # type: ignore


def main() -> None:
    """Main"""
    parser = argparse.ArgumentParser(prog="Read values from remote config .ini file")
    parser.add_argument("--url", dest="url", type=str, default=os.getenv("PACKAGING_KEYS_CONFIG_URL"),
                        help="Url pointing to file to be read")
    parser.add_argument("--section", type=str, default="packaging", help="The config section within the .ini")
    parser.add_argument("--key", type=str, required=True, help="The config key within the section")
    args = parser.parse_args(sys.argv[1:])
    if not args.url or not args.section:
        parser.print_help(sys.stderr)
        raise SystemExit("--url or --section missing")

    log.info("%s: '%s'", args.key, get_pkg_value(args.key, args.section, args.url))


if __name__ == "__main__":
    main()
