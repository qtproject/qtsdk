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
import subprocess
import sys
from pathlib import Path
from shutil import rmtree
from typing import List

from logging_util import init_logger

log = init_logger(__name__, debug_mode=False)


def is_file_with_debug_information_windows(path: str) -> bool:
    if not path.endswith('.pdb'):
        return False
    base_path = Path(path)
    pdb = base_path.with_suffix('.pdb')
    exe = base_path.with_suffix('.exe')
    dll = base_path.with_suffix('.dll')
    if os.path.isfile(pdb) and (os.path.isfile(exe) or os.path.isfile(dll)):
        return True
    return False


def is_file_with_debug_information_mac(path: str) -> bool:
    if ".dSYM/Contents/Resources/DWARF" in path:
        return True
    return False


def file_with_debug_information_linux(file: str) -> bool:
    if file.endswith(".so") or os.access(file, os.X_OK) or file.endswith(".debug"):
        return True
    return False


def read_output(args: List[str]) -> bytes:
    with subprocess.Popen(args=args, stdout=subprocess.PIPE) as proc:
        (stdout, _) = proc.communicate()
        return stdout.rstrip()


def dump_sym(dump_syms_path: str, architecture: str, absolute_path: str, sym_path: str, verbose: bool) -> bool:
    dump_syms_command = f'{dump_syms_path} {architecture} "{absolute_path}" > "{sym_path}"'
    if verbose:
        log.info("call: %s", dump_syms_command)
    dump_syms_return = subprocess.call(dump_syms_command, shell=True)
    if os.path.exists(sym_path) and os.stat(sym_path).st_size > 0 and dump_syms_return == 0:
        return True
    raise Exception(f"dump_syms can not be called: \n{dump_syms_command}\n{dump_syms_return}")


def dump_syms(
    dump_syms_path: str,
    architectures: List[str],
    search_pathes: str,
    output_path: str,
    verbose: bool,
) -> List[str]:
    is_file_with_debug_information = {
        'darwin': is_file_with_debug_information_mac,
        'win32': is_file_with_debug_information_windows
    }[sys.platform]
    sym_filenames = []
    for search_path in search_pathes.split(","):
        for root, _, filenames in os.walk(search_path):
            for filename in filenames:
                absolute_path = os.path.join(root, filename).replace("\\", "/")
                if is_file_with_debug_information(absolute_path):
                    base_path = str(Path(absolute_path).with_suffix(""))
                    start_slash = 1
                    sym_path_base = base_path[start_slash + len(search_path):].replace("/", "_")
                    sym_filename = f"{sym_path_base}.sym"
                    sym_path = os.path.join(output_path, sym_filename)
                    if dump_sym(dump_syms_path, architectures[0], absolute_path, sym_path, verbose):
                        sym_filenames.append(sym_filename)
                    if len(architectures) == 2:
                        arch_argument_len = len("--arch ")
                        sym_filename = f"{sym_path_base}_{architectures[1][arch_argument_len:]}.sym"
                        sym_path = os.path.join(output_path, sym_filename)
                        if dump_sym(dump_syms_path, architectures[1], absolute_path, sym_path, verbose):
                            sym_filenames.append(sym_filename)
    return sym_filenames


################################################################################
def _main() -> None:
    parser = argparse.ArgumentParser(
        description="fetch Breakpad symbols",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '--dump-syms-path', required=True,
        help="path to dump_syms tool"
    )
    parser.add_argument(
        '--sentry-cli-path', required=True,
        help="path to sentry-cli tool"
    )
    parser.add_argument(
        '--search-pathes', required=True,
        help="directories where the binaries can be found, separated by comma"
    )
    parser.add_argument(
        '--architectures', default="",
        help="if there is more then one architecture for example on mac: \"x86_64,arm64\""
    )
    parser.add_argument(
        '--output-path', required=True,
        help="directory where the extracted debug information will be stored"
    )
    parser.add_argument(
        '--clean-output-path', action='store_true',
        help="empty the output directory at the beginning"
    )
    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help="Gives some output what the tool is actual doing."
    )
    args = parser.parse_args()

    # make sure we can call dump_syms
    dump_syms_output = subprocess.check_output(
        [args.dump_syms_path, '--help']
    ).decode('utf-8')

    if len(dump_syms_output) <= 0:
        raise Exception(f"dump_syms can not be called: \n{dump_syms_output}")

    if os.path.exists(args.output_path):
        if args.clean_output_path:
            rmtree(args.output_path, ignore_errors=True)
    os.makedirs(args.output_path)

    for search_path in args.search_pathes.split(","):
        if not os.path.isdir(search_path):
            raise Exception(f"search_path does not exist: {search_path}")

    architectures = args.architectures.split(",")
    if len(architectures) == 2:
        architectures[0] = f"--arch {architectures[0]}"
        architectures[1] = f"--arch {architectures[1]}"
    elif args.architectures != "":
        architectures = [f"--arch {args.architectures}"]

    sym_filenames = dump_syms(args.dump_syms_path,
                              architectures,
                              args.search_pathes,
                              args.output_path,
                              args.verbose)
    if len(sym_filenames) == 0:
        raise Exception(f"no debug information files found in {args.search_pathes}")

    source_bundle_command = [args.sentry_cli_path, "difutil", "bundle-sources"]
    source_bundle_command.extend(sym_filenames)
    if args.verbose:
        log.info(source_bundle_command)
    testoutput = subprocess.check_output(
        source_bundle_command, cwd=args.output_path
    ).decode('utf-8')
    log.info(testoutput)


if __name__ == '__main__':
    # use everything capsulated in functions to make sure we are not using module globals
    _main()
