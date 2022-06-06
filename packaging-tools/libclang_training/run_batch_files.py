#!/usr/bin/env python3
# -*- coding: utf-8 -*-

############################################################################
#
# Copyright (C) 2022 The Qt Company Ltd.
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
Run Qt Creator in 'clang batch file' mode and produce csv data of resulting
libclang operations (e.g. parse, reparse, completion, preamble generation).

Multiple batch files and libclang binaries can be specified for the runs, thus
producing data for an overview of libclang's performance in certain use cases
over multiple libclang binaries/versions.

The process environment configures this script. The relevant variables and their
meaning are shown in this pseudo code of the main algorithm:

  for libclang in QTC_CLANG_BATCH_CONFIG_LIBCLANGS
     copy libclang to QTC_CLANG_BATCH_CONFIG_TARGET_LIBCLANG
          for batchfile in QTC_CLANG_BATCH_CONFIG_FILES
              run qtcreator with batchfile
              write log/csv data files into QTC_CLANG_BATCH_CONFIG_LOG_DIR
  merge csv data files per batch file.

The PATH must contain:
 * qtcreator executable and everything needed to run it.
 * qmake is in PATH for proper set up of an automatically created kit.
 * dbgview.exe on Windows since this is used to capture the output.

Notes:
 * For convenience, create a *.sh/*.bat file setting up and running this script.
 * Ensure that the specified libclang binaries expect the same intrinsics
   (<libclang install dir>/lib/clang/x.y.z/include) since these are not copied!
"""

import os
import sys
from shutil import copyfile
from subprocess import STDOUT, Popen
from time import sleep, time
from typing import Dict, List, Optional

import libclangtimings2csv
import merge_csv_files


def verbose_start(args: List[str]) -> None:
    if Config.Verbose:
        print(f"info: starting {args}")


def check_existence_or_die(file_path: str) -> None:
    if not os.path.exists(file_path):
        print(f"error: file path does not exist: {file_path}", file=sys.stderr)
        sys.exit(1)


def check_exit_code_or_die(exit_code: int, args: List[str]) -> None:
    if exit_code != 0:
        print(f"error: exit code is, {exit_code} for", ' '.join(args), file=sys.stderr)
        sys.exit(1)


class Config:
    Verbose: bool = False
    # Verbose = True

    LogDir: str = ""
    QtCreatorSettingsDir: str = ""
    TargetLibClangDll: str = ""

    LibClangDlls: List[str] = []
    BatchFiles: List[str] = []

    @staticmethod
    def initialize_from_environment() -> None:
        Config.LogDir = os.environ['QTC_CLANG_BATCH_CONFIG_LOG_DIR']
        check_existence_or_die(Config.LogDir)

        Config.QtCreatorSettingsDir = os.environ['QTC_CLANG_BATCH_CONFIG_SETTINGS_DIR']
        check_existence_or_die(Config.QtCreatorSettingsDir)

        Config.TargetLibClangDll = os.environ['QTC_CLANG_BATCH_CONFIG_TARGET_LIBCLANG']

        libclang_dlls = os.environ['QTC_CLANG_BATCH_CONFIG_LIBCLANGS']
        Config.LibClangDlls = libclang_dlls.split(os.pathsep)
        assert len(Config.LibClangDlls) >= 1
        for dll in Config.LibClangDlls:
            check_existence_or_die(dll)

        batch_files = os.environ['QTC_CLANG_BATCH_CONFIG_FILES']
        Config.BatchFiles = batch_files.split(os.pathsep)
        assert len(Config.BatchFiles) >= 1
        for batch_file in Config.BatchFiles:
            check_existence_or_die(batch_file)
            # TODO: Check for format

    @staticmethod
    def dump() -> None:
        print("log dir:")
        print(f"  {Config.LogDir}")
        print("qt creator settings dir:")
        print(f"  {Config.QtCreatorSettingsDir}")
        print("target libclang:")
        print(f"  {Config.TargetLibClangDll}")
        print("libclangs:")
        for dll in Config.LibClangDlls:
            print(f"  {dll}")
        print("batch files:")
        for batch_file in Config.BatchFiles:
            print(f"  {batch_file}")


class RunRecord:
    def __init__(self, libclang_id: str, batch_file_path: str):
        self.libclang_id = libclang_id
        parts = os.path.basename(batch_file_path).split('.')
        self.batch_file_id = '.'.join(parts[0:-1])  # Remove suffix
        self.log_file_path = self.batch_file_id + '___' + libclang_id + '.log'
        self.csv_file_path = ""


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


def create_environment(batch_file_path: str) -> Dict[str, str]:
    env = os.environ.copy()
    env['LIBCLANG_TIMING'] = '1'
    env['QT_LOGGING_RULES'] = 'qtc.clangcodemodel.batch=true'
    env['QTC_NO_CODE_INDEXER'] = '1'
    env['QTC_CLANG_NO_ALIVE_TIMER'] = '1'
    env['QTC_CLANG_NO_SUPPORTIVE_TRANSLATIONUNIT'] = '1'
    env['QTC_CLANG_BATCH_TIMEOUT'] = '3000000'
    env['QTC_CLANG_BATCH'] = batch_file_path

    return env


def run_sync_and_log_output_windows(args: List[str], batch_file_path: str, log_file_path: str) -> None:
    debug_view = DebugView(log_file_path)
    debug_view.start_async()

    verbose_start(args)
    with Popen(args, env=create_environment(batch_file_path)) as proc:
        proc.communicate()

        debug_view.stop()

        check_exit_code_or_die(proc.returncode, args)


def run_sync_and_log_output_unix(args: List[str], batch_file_path: str, log_file_path: str) -> None:
    with open(log_file_path, 'w', encoding="utf-8") as log_file:
        verbose_start(args)
        with Popen(args, stdout=log_file, stderr=STDOUT, env=create_environment(batch_file_path)) as proc:
            proc.communicate()
            check_exit_code_or_die(proc.returncode, args)


def run_qtcreator_with_batch_file(batch_file_path: str, log_file_path: str) -> None:
    args = [
        'qtcreator',
        '-noload', 'all',
        '-load', 'CppEditor',
        '-load', 'QmakeProjectManager',
        '-load', 'ClangCodeModel',
        '-load', 'Designer',
        '-settingspath',
        Config.QtCreatorSettingsDir,
    ]

    if sys.platform == "win32":
        run_sync_and_log_output_windows(args, batch_file_path, log_file_path)
    else:
        run_sync_and_log_output_unix(args, batch_file_path, log_file_path)


def convert_log_file_to_csv_file(log_file_path: str, column_label: str) -> str:
    output = libclangtimings2csv.convert(log_file_path, column_label)

    csv_file_path = log_file_path + '.csv'
    with open(csv_file_path, 'w', encoding="utf-8") as handle:
        handle.write(output)

    return csv_file_path


def log_file_from_id(log_file_id: str) -> str:
    return log_file_id + ".log"


def create_dir(dir_path: str) -> None:
    if not os.path.exists(dir_path):
        if Config.Verbose:
            print(f"info: creating not existent {dir_path}")
        os.makedirs(dir_path)


def create_backup_file(file_path: str) -> None:
    if os.path.exists(file_path):
        backup_path = file_path[:-4] + ".backup_" + str(time()) + ".log"
        if Config.Verbose:
            print(f"info: creating backup of already existing '{file_path}'")
        copyfile(file_path, backup_path)


def print_duration(seconds: float) -> None:
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    print(f"...needed {hours}:{minutes}:{seconds}")


def process_batch_file_timed(libclang_id: str, batch_file_path: str) -> RunRecord:
    time_started = time()
    print(f"processing {batch_file_path}", end=' ')

    run_record = process_batch_file(libclang_id, batch_file_path)

    print_duration(time() - time_started)

    return run_record


def process_batch_file(libclang_id: str, batch_file_path: str) -> RunRecord:
    run_record = RunRecord(libclang_id, batch_file_path)
    log_file_path = os.path.join(Config.LogDir, run_record.log_file_path)

    create_dir(Config.LogDir)
    create_backup_file(log_file_path)

    run_qtcreator_with_batch_file(batch_file_path, log_file_path)

    csv_file_path = convert_log_file_to_csv_file(log_file_path, run_record.libclang_id)
    run_record.csv_file_path = csv_file_path

    return run_record


def get_libclang_id(libclang_dll: str) -> str:
    file_name = os.path.basename(libclang_dll)
    parts = file_name.split('.')
    identifier = '.'.join(parts[0:-1])
    return identifier


def switch_libclang(libclang_dll: str) -> None:
    print(f"copying '{libclang_dll}' -> '{Config.TargetLibClangDll}'")
    copyfile(libclang_dll, Config.TargetLibClangDll)


def run_qtcreator_with_libclang(libclang_dll: str) -> List[RunRecord]:
    print("")
    switch_libclang(libclang_dll)

    run_records = []
    libclang_id = get_libclang_id(libclang_dll)
    for batch_file in Config.BatchFiles:
        run_record = process_batch_file_timed(libclang_id, batch_file)
        run_records.append(run_record)

    return run_records


def log_id_part_from_libclang_dll(libclang_dll: str) -> str:
    file_name = os.path.basename(libclang_dll)
    parts = file_name.split('.')
    file_name = '.'.join(parts[1:-1])
    return file_name


def merge_generated_csv_files(run_records: List[RunRecord]) -> None:
    batch_file_id_2_run_record: Dict[str, List[RunRecord]] = {}
    for run_record in run_records:
        new_value = [run_record]
        if run_record.batch_file_id in batch_file_id_2_run_record:
            new_value = batch_file_id_2_run_record[run_record.batch_file_id]
            new_value.append(run_record)
        batch_file_id_2_run_record[run_record.batch_file_id] = new_value

    for batch_file_id, runrecord_list in batch_file_id_2_run_record.items():
        csv_file_paths = [run_record.csv_file_path for run_record in runrecord_list]
        merge_file_path = os.path.join(Config.LogDir, batch_file_id + ".csv")

        merge_csv_files.merge_files(merge_file_path, csv_file_paths)
        print(f"generated: {merge_file_path}")


def main() -> None:
    Config.initialize_from_environment()
    Config.dump()

    run_records = []
    for libclang_dll in Config.LibClangDlls:
        run_records += run_qtcreator_with_libclang(libclang_dll)

    print()
    merge_generated_csv_files(run_records)


if __name__ == "__main__":
    main()
