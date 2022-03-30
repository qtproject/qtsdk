#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#############################################################################
##
## Copyright (C) 2022 The Qt Company Ltd.
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
from configparser import ConfigParser
import argparse
import os
import sys


class PackagingOptions:
    """Utility class to read options from configuration file that follows .ini file format."""
    def __init__(self, confFile):
        if not os.path.isfile(confFile):
            raise IOError("Not a valid file: {0}".format(confFile))
        self.config = ConfigParser.ConfigParser(os.environ)
        self.config.optionxform = str
        self.config.read(confFile)

    def configSectionMap(self, section):
        dict1 = {}
        options = self.config.options(section)
        for option in options:
            try:
                dict1[option] = self.config.get(section, option)
                if dict1[option] == -1:
                    print("skip: %s" % option)
            except:
                print("exception on %s!" % option)
                dict1[option] = None
        return dict1

    def sectionExists(self, section):
        return self.config.has_section(section)

    def optionExists(self, section, option):
        return self.sectionExists(section) and self.config.has_option(section, option)

    def configMap(self):
        dict1 = {}
        for section in self.config.sections():
            dict1.update(self.configSectionMap(section))
        return dict1

    def verbose(self):
        for section in self.config.sections():
            print("[" + section + "]")
            options = self.config.options(section)
            for option in options:
                print("{0} = {1}".format(option, self.config.get(section, option)))
            print


def getPkgOptions(confFilePath):
    return PackagingOptions(confFilePath)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog="Parse packaging related options from config file.")
    parser.add_argument("--conf-file", dest="conf_file", required=True, type=str,
                        help="Absolute path pointing into configuration file which contains all required options for packaging.")
    args = parser.parse_args(sys.argv[1:])
    # Print out all options
    options = getPkgOptions(args.conf_file)
    configMap = options.configMap()
    print(configMap)
