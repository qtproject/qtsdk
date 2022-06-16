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
import shutil
import subprocess
import sys


def is_file_with_debug_information_windows(path):
    if not path.endswith('.pdb'):
        return False
    base_path, extension = os.path.splitext(path)
    pdb = base_path + '.pdb'
    exe = base_path + '.exe'
    dll = base_path + '.dll'
    if os.path.isfile(pdb) and (os.path.isfile(exe) or os.path.isfile(dll)):
        return True
    return False

def is_file_with_debug_information_mac(path):
    if ".dSYM/Contents/Resources/DWARF" in path:
        return True
    return False

def file_with_debug_information_linux():
    if file.endswith(".so") or os.access(file, os.X_OK) or file.endswith(".debug"):
        return True
    return False

def read_output(*args):
    (stdout, _) = subprocess.Popen(args=args, stdout=subprocess.PIPE).communicate()
    return stdout.rstrip()

def dump_sym(dump_syms_path, architecture, absolute_path, sym_path, verbose):
    dump_syms_command = '{} {} "{}" > "{}"'.format(dump_syms_path, architecture, absolute_path, sym_path)
    if (verbose):
        print("call: {}".format(dump_syms_command))
    dump_syms_return = subprocess.call(dump_syms_command, shell=True)
    if os.path.exists(sym_path) and os.stat(sym_path).st_size > 0 and dump_syms_return == 0:
        return True
    else:
        raise Exception("dump_syms can not be called: \n{}\n{}".format(dump_syms_command, dump_syms_return))
    return False

def dump_syms(dump_syms_path, architectures, search_pathes, output_path, verbose):
    is_file_with_debug_information = {
        'darwin': is_file_with_debug_information_mac,
        'win32': is_file_with_debug_information_windows
    }[sys.platform]
    sym_filenames = []
    for search_path in search_pathes.split(","):
        for root, dirnames, filenames in os.walk(search_path):
            for filename in filenames:
                absolute_path = os.path.join(root, filename).replace("\\", "/")
                if is_file_with_debug_information(absolute_path):
                    base_path, extension = os.path.splitext(absolute_path)
                    start_slash = 1
                    sym_path_base = base_path[start_slash + len(search_path):].replace("/", "_")
                    sym_filename = "{}.sym".format(sym_path_base)
                    sym_path =  os.path.join(output_path, sym_filename)
                    if dump_sym(dump_syms_path, architectures[0], absolute_path, sym_path, verbose):
                        sym_filenames.append(sym_filename)
                    if len(architectures) == 2:
                        arch_argument_len = len("--arch ")
                        sym_filename = "{}_{}.sym".format(sym_path_base, architectures[1][arch_argument_len:])
                        sym_path =  os.path.join(output_path, sym_filename)
                        if dump_sym(dump_syms_path, architectures[1], absolute_path, sym_path, verbose):
                            sym_filenames.append(sym_filename)
    return sym_filenames

################################################################################
def _main():
    parser = argparse.ArgumentParser(description="fetch Breakpad symbols",
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--dump-syms-path', required=True,
        help="path to dump_syms tool")
    parser.add_argument('--sentry-cli-path', required=True,
        help="path to sentry-cli tool")
    parser.add_argument('--search-pathes', required=True,
        help="directories where the binaries can be found, separated by comma")
    parser.add_argument('--architectures', default="",
        help="if there is more then one architecture for example on mac: \"x86_64,arm64\"")
    parser.add_argument('--output-path', required=True,
        help="directory where the extracted debug information will be stored")
    parser.add_argument('--clean-output-path', action='store_true',
        help="empty the output directory at the beginning")
    parser.add_argument('-v', '--verbose', action='store_true',
        help="Gives some output what the tool is actual doing.")
    args = parser.parse_args()

    # make sure we can call dump_syms
    dump_syms_output = subprocess.check_output(
              [args.dump_syms_path, '--help']).decode('utf-8')

    if len(dump_syms_output) <= 0:
        raise Exception("dump_syms can not be called: \n{}".format(dump_syms_output))

    if os.path.exists(args.output_path):
        if args.clean_output_path:
            shutil.rmtree(args.output_path, ignore_errors=True)
    os.makedirs(args.output_path)

    for search_path in args.search_pathes.split(","):
        if not os.path.isdir(search_path):
            raise Exception("search_path does not exist: {}".format(search_path))

    architectures = args.architectures.split(",")
    if len(architectures) == 2:
        architectures[0] = "--arch {}".format(architectures[0])
        architectures[1] = "--arch {}".format(architectures[1])
    elif args.architectures != "":
        architectures = ["--arch {}".format(args.architectures)]

    sym_filenames = dump_syms(args.dump_syms_path,
                              architectures,
                              args.search_pathes,
                              args.output_path,
                              args.verbose)
    if len(sym_filenames) == 0:
        raise Exception("no debug information files found in {}".format(args.search_pathes))

    source_bundle_command = [args.sentry_cli_path, "difutil", "bundle-sources"]
    source_bundle_command.extend(sym_filenames)
    if args.verbose:
        print(source_bundle_command)
    testoutput = subprocess.check_output(
              source_bundle_command, cwd=args.output_path).decode('utf-8')
    print(testoutput)

    return

if __name__ == '__main__':
    # use everything capsulated in functions to make sure we are not using module globals
    _main()
