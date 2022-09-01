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
from typing import List

import libclangtimings2csv
import mergeCsvFiles


def verbose_start(args):
    if Config.Verbose:
        print(f"info: starting {args}")


def check_existence_or_die(file_path):
    if not os.path.exists(file_path):
        print(f"error: file path does not exist: {file_path}", file=sys.stderr)
        sys.exit(1)


def check_exit_code_or_die(exit_code, args):
    if exit_code != 0:
        print(f"error: exit code is, {exit_code} for", ' '.join(args), file=sys.stderr)
        sys.exit(1)


class Config:
    Verbose = False
    # Verbose = True

    LogDir = None
    QtCreatorSettingsDir = None
    TargetLibClangDll = None

    LibClangDlls: List[str] = []
    BatchFiles: List[str] = []

    @staticmethod
    def initialize_from_environment():
        Config.LogDir = os.environ['QTC_CLANG_BATCH_CONFIG_LOG_DIR']
        check_existence_or_die(Config.LogDir)

        Config.QtCreatorSettingsDir = os.environ['QTC_CLANG_BATCH_CONFIG_SETTINGS_DIR']
        check_existence_or_die(Config.QtCreatorSettingsDir)

        Config.TargetLibClangDll = os.environ['QTC_CLANG_BATCH_CONFIG_TARGET_LIBCLANG']

        libClangDlls = os.environ['QTC_CLANG_BATCH_CONFIG_LIBCLANGS']
        Config.LibClangDlls = libClangDlls.split(os.pathsep)
        assert len(Config.LibClangDlls) >= 1
        for dll in Config.LibClangDlls:
            check_existence_or_die(dll)

        batchFiles = os.environ['QTC_CLANG_BATCH_CONFIG_FILES']
        Config.BatchFiles = batchFiles.split(os.pathsep)
        assert len(Config.BatchFiles) >= 1
        for b in Config.BatchFiles:
            check_existence_or_die(b)
            # TODO: Check for format

    @staticmethod
    def dump():
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
        for b in Config.BatchFiles:
            print(f"  {b}")


class RunRecord:
    def __init__(self, libclang_id, batch_file_path):
        self.libClangId = libclang_id
        parts = os.path.basename(batch_file_path).split('.')
        self.batchFileId = '.'.join(parts[0:-1])  # Remove suffix
        self.logFilePath = self.batchFileId + '___' + libclang_id + '.log'
        self.csvFilePath = None


class DebugView:
    def __init__(self, log_file_path):
        self.logFilePath = log_file_path
        self.executable = 'dbgview.exe'

    def start_async(self):
        args = [self.executable, '/accepteula', '/l', self.logFilePath]
        verbose_start(args)
        self.proc = Popen(args, shell=False)  # pylint: disable=R1732
        sleep(2)

    def stop(self):
        if self.proc:
            if Config.Verbose:
                print(f"info: stopping {self.executable}")
            self.proc.terminate()
            self.proc.wait()


def create_environment(batch_file_path):
    env = os.environ.copy()
    env['LIBCLANG_TIMING'] = '1'
    env['QT_LOGGING_RULES'] = 'qtc.clangcodemodel.batch=true'
    env['QTC_NO_CODE_INDEXER'] = '1'
    env['QTC_CLANG_NO_ALIVE_TIMER'] = '1'
    env['QTC_CLANG_NO_SUPPORTIVE_TRANSLATIONUNIT'] = '1'
    env['QTC_CLANG_BATCH_TIMEOUT'] = '3000000'
    env['QTC_CLANG_BATCH'] = batch_file_path

    return env


def run_sync_and_log_output_windows(args, batch_file_path, log_file_path):
    debugView = DebugView(log_file_path)
    debugView.start_async()

    verbose_start(args)
    with Popen(args, env=create_environment(batch_file_path)) as p:
        p.communicate()

        debugView.stop()

        check_exit_code_or_die(p.returncode, args)


def run_sync_and_log_output_unix(args, batch_file_path, log_file_path):
    with open(log_file_path, "w", encoding="utf-8") as logFile:
        verbose_start(args)
        with Popen(args, stdout=logFile, stderr=STDOUT, env=create_environment(batch_file_path)) as p:
            p.communicate()
            check_exit_code_or_die(p.returncode, args)


def run_qtcreator_with_batch_file(batch_file_path, log_file_path):
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


def convert_log_file_to_csv_file(log_file_path, column_label):
    output = libclangtimings2csv.convert(log_file_path, column_label)

    csvFilePath = log_file_path + '.csv'
    with open(csvFilePath, 'w', encoding="utf-8") as f:
        f.write(output)

    return csvFilePath


def log_file_from_id(log_file_id):
    return log_file_id + ".log"


def create_dir(dir_path):
    if not os.path.exists(dir_path):
        if Config.Verbose:
            print(f"info: creating not existent {dir_path}")
        os.makedirs(dir_path)


def create_backup_file(file_path):
    if os.path.exists(file_path):
        backupPath = file_path[:-4] + ".backup_" + str(time()) + ".log"
        if Config.Verbose:
            print(f"info: creating backup of already existing '{file_path}'")
        copyfile(file_path, backupPath)


def print_duration(s):
    hours, remainder = divmod(s, 3600)
    minutes, seconds = divmod(remainder, 60)
    print(f"...needed {hours}:{minutes}:{seconds}")


def process_batch_file_timed(libclang_id, batch_file_path):
    timeStarted = time()
    print(f"processing {batch_file_path}", end=' ')

    runRecord = process_batch_file(libclang_id, batch_file_path)

    print_duration(time() - timeStarted)

    return runRecord


def process_batch_file(libclang_id, batch_file_path):
    runRecord = RunRecord(libclang_id, batch_file_path)
    logFilePath = os.path.join(Config.LogDir, runRecord.logFilePath)

    create_dir(Config.LogDir)
    create_backup_file(logFilePath)

    run_qtcreator_with_batch_file(batch_file_path, logFilePath)

    csvFilePath = convert_log_file_to_csv_file(logFilePath, runRecord.libClangId)
    runRecord.csvFilePath = csvFilePath

    return runRecord


def get_libclang_id(libclang_dll):
    fileName = os.path.basename(libclang_dll)
    parts = fileName.split('.')
    identifier = '.'.join(parts[0:-1])
    return identifier


def switch_libclang(libclang_dll):
    print(f"copying '{libclang_dll}' -> '{Config.TargetLibClangDll}'")
    copyfile(libclang_dll, Config.TargetLibClangDll)


def run_qtcreator_with_libclang(libclang_dll):
    print("")
    switch_libclang(libclang_dll)

    runRecords = []
    libClangId = get_libclang_id(libclang_dll)
    for batchFile in Config.BatchFiles:
        runRecord = process_batch_file_timed(libClangId, batchFile)
        runRecords.append(runRecord)

    return runRecords


def log_id_part_from_libclang_dll(libclang_dll):
    fileName = os.path.basename(libclang_dll)
    parts = fileName.split('.')
    fileName = '.'.join(parts[1:-1])
    return fileName


def merge_generated_csv_files(run_records):
    batchFileId2RunRecord = {}
    for rr in run_records:
        newValue = [rr]
        if rr.batchFileId in batchFileId2RunRecord:
            newValue = batchFileId2RunRecord[rr.batchFileId]
            newValue.append(rr)
        batchFileId2RunRecord[rr.batchFileId] = newValue

    for batchFileId in batchFileId2RunRecord:
        csvFilePaths = [rr.csvFilePath for rr in batchFileId2RunRecord[batchFileId]]
        mergeFilePath = os.path.join(Config.LogDir, batchFileId + ".csv")

        mergeCsvFiles.merge_files(mergeFilePath, csvFilePaths)
        print(f"generated: {mergeFilePath}")


def main():
    Config.initialize_from_environment()
    Config.dump()

    runRecords = []
    for libClangDll in Config.LibClangDlls:
        runRecords += run_qtcreator_with_libclang(libClangDll)

    print()
    merge_generated_csv_files(runRecords)


if __name__ == "__main__":
    main()
