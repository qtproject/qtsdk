#!/usr/bin/env python3
# -*- coding: utf-8 -*-

############################################################################
#
# Copyright (C) 2023 The Qt Company Ltd.
# Contact: https://www.qt.io/licensing/
#
# This file is part of Qt Creator.
#
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
############################################################################

"""
Run Qt Creator with the the ClangCodeModel tests

The PATH must contain:
 * qtcreator executable and everything needed to run it.
 * qmake is in PATH for proper set up of an automatically created kit.
 * dbgview.exe on Windows since this is used to capture the output.

"""

import os
import sys
from pathlib import Path
from shutil import copyfile
from subprocess import STDOUT, Popen
from time import sleep, time
from typing import Dict, List, Optional

def verbose_start(args: List[str]) -> None:
    if Config.Verbose:
        print(f"info: starting {args}")


def check_existence_or_die(file_path: str) -> None:
    if not os.path.exists(file_path):
        raise SystemExit(f"file path does not exist: {file_path}")


def check_exit_code(exit_code: int, args: List[str]) -> None:
    if exit_code != 0:
        print(f"Exit code {exit_code} for {' '.join(args)}")


class Config:
    Verbose: bool = False
    # Verbose = True

    LogDir: str = ""
    QtCreatorSettingsDir: str = ""

    @staticmethod
    def initialize_from_environment() -> None:
        Config.LogDir = os.environ['QTC_CLANGD_CONFIG_LOG_DIR']
        check_existence_or_die(Config.LogDir)

        Config.QtCreatorSettingsDir = os.environ['QTC_CLANGD_CONFIG_SETTINGS_DIR']
        check_existence_or_die(Config.QtCreatorSettingsDir)

    @staticmethod
    def dump() -> None:
        print("log dir:")
        print(f"  {Config.LogDir}")
        print("qt creator settings dir:")
        print(f"  {Config.QtCreatorSettingsDir}")


class DebugView:
    def __init__(self, log_file_path: str):
        self.log_file_path = log_file_path
        self.executable = 'dbgview.exe'
        self.proc: Optional[Popen] = None  # type: ignore

    def start_async(self) -> None:
        args = [self.executable, '/accepteula', '/l', self.log_file_path]
        verbose_start(args)
        self.proc = Popen(args, shell=False)  # pylint: disable=R1732
        sleep(2)

    def stop(self) -> None:
        if self.proc:
            if Config.Verbose:
                print(f"info: stopping {self.executable}")
            self.proc.terminate()
            self.proc.wait()


def create_environment() -> Dict[str, str]:
    env = os.environ.copy()
    env['QT_LOGGING_RULES'] = 'qtc.clangcodemodel.clangd=true;qtc.clangcodemodel.clangd.timing=true'

    return env

def run_sync_and_log_output_windows(args: List[str], log_file_path: str) -> None:
    debug_view = DebugView(log_file_path)
    debug_view.start_async()

    verbose_start(args)
    with Popen(args, env=create_environment()) as proc:
        proc.communicate()

        debug_view.stop()

        check_exit_code(proc.returncode, args)


def run_sync_and_log_output_unix(args: List[str], log_file_path: str) -> None:
    with open(log_file_path, 'w', encoding="utf-8") as log_file:
        verbose_start(args)
        with Popen(args, stdout=log_file, stderr=STDOUT, env=create_environment()) as proc:
            proc.communicate()
            check_exit_code(proc.returncode, args)


def run_qtcreator_with_log_file(log_file_path: str) -> None:
    args = [
        'qtcreator',
        '-settingspath',
        Config.QtCreatorSettingsDir,
        '-test', 'ClangCodeModel'
    ]

    if sys.platform == "win32":
        run_sync_and_log_output_windows(args, log_file_path)
    else:
        run_sync_and_log_output_unix(args, log_file_path)


def create_dir(dir_path: str) -> None:
    if not os.path.exists(dir_path):
        if Config.Verbose:
            print(f"info: creating not existent {dir_path}")
        Path(dir_path).mkdir(parents=True)

def main() -> None:
    Config.initialize_from_environment()
    Config.dump()

    log_file_path = os.path.join(Config.LogDir, "qtcreator.log")
    create_dir(Config.LogDir)

    run_qtcreator_with_log_file(log_file_path)

    with open(log_file_path) as log:
        print(log.read())

if __name__ == "__main__":
    main()
