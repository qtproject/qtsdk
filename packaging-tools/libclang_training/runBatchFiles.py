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


def verboseStart(args):
    if Config.Verbose:
        print(f"info: starting {args}")


def checkExistenceOrDie(filePath):
    if not os.path.exists(filePath):
        print(f"error: file path does not exist: {filePath}", file=sys.stderr)
        sys.exit(1)


def checkExitCodeOrDie(exitCode, args):
    if exitCode != 0:
        print(f"error: exit code is, {exitCode} for", ' '.join(args), file=sys.stderr)
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
    def initializeFromEnvironment():
        Config.LogDir = os.environ['QTC_CLANG_BATCH_CONFIG_LOG_DIR']
        checkExistenceOrDie(Config.LogDir)

        Config.QtCreatorSettingsDir = os.environ['QTC_CLANG_BATCH_CONFIG_SETTINGS_DIR']
        checkExistenceOrDie(Config.QtCreatorSettingsDir)

        Config.TargetLibClangDll = os.environ['QTC_CLANG_BATCH_CONFIG_TARGET_LIBCLANG']

        libClangDlls = os.environ['QTC_CLANG_BATCH_CONFIG_LIBCLANGS']
        Config.LibClangDlls = libClangDlls.split(os.pathsep)
        assert len(Config.LibClangDlls) >= 1
        for dll in Config.LibClangDlls:
            checkExistenceOrDie(dll)

        batchFiles = os.environ['QTC_CLANG_BATCH_CONFIG_FILES']
        Config.BatchFiles = batchFiles.split(os.pathsep)
        assert len(Config.BatchFiles) >= 1
        for b in Config.BatchFiles:
            checkExistenceOrDie(b)
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
    def __init__(self, libClangId, batchFilePath):
        self.libClangId = libClangId
        parts = os.path.basename(batchFilePath).split('.')
        self.batchFileId = '.'.join(parts[0:-1])  # Remove suffix
        self.logFilePath = self.batchFileId + '___' + libClangId + '.log'
        self.csvFilePath = None


class DebugView:
    def __init__(self, logFilePath):
        self.logFilePath = logFilePath
        self.executable = 'dbgview.exe'

    def startAsync(self):
        args = [self.executable, '/accepteula', '/l', self.logFilePath]
        verboseStart(args)
        self.proc = Popen(args, shell=False)
        sleep(2)

    def stop(self):
        if self.proc:
            if Config.Verbose:
                print(f"info: stopping {self.executable}")
            self.proc.terminate()
            self.proc.wait()


def createEnvironment(batchFilePath):
    env = os.environ.copy()
    env['LIBCLANG_TIMING'] = '1'
    env['QT_LOGGING_RULES'] = 'qtc.clangcodemodel.batch=true'
    env['QTC_NO_CODE_INDEXER'] = '1'
    env['QTC_CLANG_NO_ALIVE_TIMER'] = '1'
    env['QTC_CLANG_NO_SUPPORTIVE_TRANSLATIONUNIT'] = '1'
    env['QTC_CLANG_BATCH_TIMEOUT'] = '3000000'
    env['QTC_CLANG_BATCH'] = batchFilePath

    return env


def runSyncAndLogOutputWindows(args, batchFilePath, logFilePath):
    debugView = DebugView(logFilePath)
    debugView.startAsync()

    verboseStart(args)
    p = Popen(args, env=createEnvironment(batchFilePath))
    p.communicate()

    debugView.stop()

    checkExitCodeOrDie(p.returncode, args)


def runSyncAndLogOutputUnix(args, batchFilePath, logFilePath):
    logFile = open(logFilePath, 'w')

    verboseStart(args)
    p = Popen(args,
              stdout=logFile,
              stderr=STDOUT,
              env=createEnvironment(batchFilePath))
    p.communicate()

    checkExitCodeOrDie(p.returncode, args)


def runQtCreatorWithBatchFile(batchFilePath, logFilePath):
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
        runSyncAndLogOutputWindows(args, batchFilePath, logFilePath)
    else:
        runSyncAndLogOutputUnix(args, batchFilePath, logFilePath)


def convertLogFileToCsvFile(logFilePath, columnLabel):
    output = libclangtimings2csv.convert(logFilePath, columnLabel)

    csvFilePath = logFilePath + '.csv'
    f = open(csvFilePath, 'w')
    f.write(output)
    f.close()

    return csvFilePath


def logFileFromId(logFileId):
    return logFileId + ".log"


def createDir(dirPath):
    if not os.path.exists(dirPath):
        if Config.Verbose:
            print(f"info: creating not existent {dirPath}")
        os.makedirs(dirPath)


def createBackupFile(filePath):
    if os.path.exists(filePath):
        backupPath = filePath[:-4] + ".backup_" + str(time()) + ".log"
        if Config.Verbose:
            print(f"info: creating backup of already existing '{filePath}'")
        copyfile(filePath, backupPath)


def printDuration(s):
    hours, remainder = divmod(s, 3600)
    minutes, seconds = divmod(remainder, 60)
    print(f"...needed {hours}:{minutes}:{seconds}")


def processBatchFileTimed(libClangId, batchFilePath):
    timeStarted = time()
    print(f"processing {batchFilePath}", end=' ')

    runRecord = processBatchFile(libClangId, batchFilePath)

    printDuration(time() - timeStarted)

    return runRecord


def processBatchFile(libClangId, batchFilePath):
    runRecord = RunRecord(libClangId, batchFilePath)
    logFilePath = os.path.join(Config.LogDir, runRecord.logFilePath)

    createDir(Config.LogDir)
    createBackupFile(logFilePath)

    runQtCreatorWithBatchFile(batchFilePath, logFilePath)

    csvFilePath = convertLogFileToCsvFile(logFilePath, runRecord.libClangId)
    runRecord.csvFilePath = csvFilePath

    return runRecord


def getLibClangId(libClangDll):
    fileName = os.path.basename(libClangDll)
    parts = fileName.split('.')
    identifier = '.'.join(parts[0:-1])
    return identifier


def switchLibClang(libClangDll):
    print(f"copying '{libClangDll}' -> '{Config.TargetLibClangDll}'")
    copyfile(libClangDll, Config.TargetLibClangDll)


def runQtCreatorWithLibClang(libClangDll):
    print("")
    switchLibClang(libClangDll)

    runRecords = []
    libClangId = getLibClangId(libClangDll)
    for batchFile in Config.BatchFiles:
        runRecord = processBatchFileTimed(libClangId, batchFile)
        runRecords.append(runRecord)

    return runRecords


def logIdPartFromLibClangDll(libClangDll):
    fileName = os.path.basename(libClangDll)
    parts = fileName.split('.')
    fileName = '.'.join(parts[1:-1])
    return fileName


def mergeGeneratedCsvFiles(runRecords):
    batchFileId2RunRecord = {}
    for rr in runRecords:
        newValue = [rr]
        if rr.batchFileId in batchFileId2RunRecord:
            newValue = batchFileId2RunRecord[rr.batchFileId]
            newValue.append(rr)
        batchFileId2RunRecord[rr.batchFileId] = newValue

    for batchFileId in batchFileId2RunRecord:
        csvFilePaths = [rr.csvFilePath for rr in batchFileId2RunRecord[batchFileId]]
        mergeFilePath = os.path.join(Config.LogDir, batchFileId + ".csv")

        mergeCsvFiles.mergeFiles(mergeFilePath, csvFilePaths)
        print(f"generated: {mergeFilePath}")


def main():
    Config.initializeFromEnvironment()
    Config.dump()

    runRecords = []
    for libClangDll in Config.LibClangDlls:
        runRecords += runQtCreatorWithLibClang(libClangDll)

    print
    mergeGeneratedCsvFiles(runRecords)


if __name__ == "__main__":
    main()
