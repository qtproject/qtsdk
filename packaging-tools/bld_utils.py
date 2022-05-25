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

import os
import shutil
import sys
from builtins import OSError
from collections import deque
from copy import deepcopy
from distutils.spawn import find_executable  # runCommand method
from socket import setdefaulttimeout
from subprocess import PIPE, STDOUT, Popen
from sys import platform
from threading import currentThread
from time import sleep
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse
from urllib.request import pathname2url, urlopen

# 3rd party module to read process output in a convenient way
from asynchronousfilereader import AsynchronousFileReader

# make a timeout for download jobs
setdefaulttimeout(30)


def is_windows() -> bool:
    """Return True if the current platform is Windows. False otherwise."""
    return platform == "win32"


def is_macos() -> bool:
    """Return True if the current platform is Darwin. False otherwise."""
    return platform == "darwin"


def is_linux() -> bool:
    """Return True if the current platform is Linux. False otherwise."""
    return platform == "linux"


# make sure any argument is deep copied, for example the install command changes the makeflags,
# but should not do that on the further used environment dict
def deep_copy_arguments(to_call):
    def f(*args, **kwargs):
        return to_call(*(deepcopy(x) for x in args),
                       **{k: deepcopy(v) for k, v in kwargs.items()})
    return f


class DirRenamer(object):

    def __init__(self, path, newName):
        self.oldName = path
        self.newName = os.path.join(os.path.split(path)[0], newName)
        print("self.oldName: " + self.oldName)
        print("self.newName: " + self.newName)

    def __enter__(self):
        if self.oldName != self.newName:
            os.rename(self.oldName, self.newName)

    def __exit__(self, etype, value, etraceback):
        if self.oldName != self.newName:
            os.rename(self.newName, self.oldName)


def compress(path, directoryName, sevenZipTarget, callerArguments):
    sevenZipExtension = os.extsep + '7z'
    parentDirectoryPath = os.path.abspath(os.path.join(path, '..'))
    if os.path.splitext(sevenZipTarget)[1] != sevenZipExtension:
        sevenZipTarget = sevenZipTarget + sevenZipExtension
    sevenZipFileName = os.path.split(sevenZipTarget)[1]
    with DirRenamer(path, directoryName):
        runCommand(' '.join(('7z a -mx9', sevenZipFileName, directoryName)), parentDirectoryPath, callerArguments)

    currentSevenZipPath = os.path.join(parentDirectoryPath, sevenZipFileName)
    if currentSevenZipPath != sevenZipTarget:
        shutil.move(currentSevenZipPath, sevenZipTarget)


def stripVars(sobject, chars):
    for key, value in vars(sobject).items():
        if isinstance(value, str):
            setattr(sobject, key, value.strip(chars))


def urllib2_response_read(response, file_path, block_size, total_size):
    total_size = int(total_size)
    bytes_count = 0

    filename = open(file_path, 'wb')
    old_percent = -1
    while 1:
        block = response.read(block_size)
        filename.write(block)
        bytes_count += len(block)

        if not block:
            break

        percent = min(100, bytes_count * 100 / total_size)
        if percent != old_percent:
            sys.stdout.write("\r{}%".format(percent))
        old_percent = percent

    filename.close()
    return bytes_count


def download(url, target, read_block_size=1048576):
    try:
        if os.path.isdir(os.path.abspath(target)):
            filename = os.path.basename(urlparse(url).path)
            target = os.path.join(os.path.abspath(target), filename)
        if os.path.lexists(target):
            raise Exception("Can not download '{0}' to '{1}' as target. The file already exists.".format(url, target))

        def localDownload(localFilePath, targtFilePath):
            if os.path.isfile(localFilePath):
                print("copying file from '{0}' to {1}".format(localFilePath, targtFilePath))
                try:
                    os.makedirs(os.path.dirname(targtFilePath))
                except Exception:
                    pass
                shutil.copy2(localFilePath, target)
                print("Done" + os.linesep)

        if os.path.lexists(url[len("file:///"):]):
            # because scheme of a absolute windows path is the drive letter in python 2,
            # we need to use file:// as a work around in urls
            localDownload(url[len("file:///"):], target)
            return
        # there is code which only have two slashes - protocol://host/path <- localhost can be omitted
        if os.path.lexists(url[len("file://"):]):
            localDownload(url[len("file://"):], target)
            return
        if os.path.lexists(url):
            localDownload(url, target)
            return

        savefile_tmp = os.extsep.join((target, 'tmp'))
        try:
            os.makedirs(os.path.dirname(savefile_tmp))
        except Exception:
            pass

        try:
            # use urlopen which raise an error if that file is not existing
            response = urlopen(url)
            total_size = response.info().get('Content-Length').strip()
            print("Downloading file from '{0}' with size {1} bytes to {2}".format(url, total_size, target))
            # run the download
            received_size = urllib2_response_read(response, savefile_tmp, read_block_size, total_size)
            if received_size != int(total_size):
                raise Exception("Broken download, got a wrong size after download from '{0}'(total size: {1}, but {2} received).".format(url, total_size, received_size))
        except HTTPError as error:
            raise Exception("Can not download '{0}' to '{1}' as target(error code: '{2}').".format(url, target, error.code))

        renamed = False
        tryRenameCounter = 0
        while renamed is False :
            tryRenameCounter = tryRenameCounter + 1
            try:
                if tryRenameCounter > 5 :
                    sys.stdout.write("r{0}".format(tryRenameCounter))
                if os.path.lexists(target):
                    raise Exception("Please remove savefile first: {0}".format(target))
                os.rename(savefile_tmp, target)
                if not os.path.lexists(savefile_tmp):
                    renamed = True
                    # make sure that another output starts in a new line
                    sys.stdout.write(os.linesep)
            except OSError as e:
                # if it still exists just try that after a microsleep and stop this after 720 tries
                if os.path.lexists(savefile_tmp) and tryRenameCounter < 720:
                    sleep(2)
                    continue
                else:
                    if not os.path.lexists(target):
                        raise Exception("Could not rename {0} to {1}{2}Error: {3}".format(savefile_tmp, target, os.linesep, e.message))
    finally:  # this is done before the except code is called
        try:
            os.remove(savefile_tmp)
        except Exception:  # swallow, do not shadow actual error
            pass


def setValueOnEnvironmentDict(environment, key, value):
    if key in environment:
        # if the data already contains the value stop here
        if value in environment[key].split(os.pathsep):
            return
        environment[key] = os.pathsep.join((value, environment[key]))
    else:
        environment[key] = value


@deep_copy_arguments
def getEnvironment(extra_environment=None, callerArguments=None):
    # first take the one from the system and use the plain dictionary data for that
    environment = dict(os.environ)

    if not extra_environment:
        return environment

    for key in extra_environment.keys():
        keyUpper = key.upper()
        if any((keyUpper == 'PATH', keyUpper == 'INCLUDE', keyUpper == 'LIB')):
            setValueOnEnvironmentDict(environment, key, extra_environment[key])
        else:
            environment[key] = extra_environment[key]
    return environment


@deep_copy_arguments
def runCommand(command, currentWorkingDirectory, callerArguments=None, extra_environment=None, onlyErrorCaseOutput=False, expectedExitCodes=[0]):
    if type(expectedExitCodes) is not list:
        raise TypeError("{}({}) is not {}".format("expectedExitCodes", type(expectedExitCodes), list))
    if type(onlyErrorCaseOutput) is not bool:
        raise TypeError("{}({}) is not {}".format("onlyErrorCaseOutput", type(onlyErrorCaseOutput), bool))

    if type(command) is list:
        commandAsList = command
    else:
        commandAsList = command[:].split(' ')

    environment = getEnvironment(extra_environment, callerArguments)

    # if we can not find the command, just check the current working dir
    if (not os.path.lexists(commandAsList[0]) and currentWorkingDirectory
            and os.path.isfile(os.path.abspath(os.path.join(currentWorkingDirectory, commandAsList[0])))):
        commandAsList[0] = os.path.abspath(os.path.join(currentWorkingDirectory, commandAsList[0]))

    pathEnvironment = environment['PATH']
    # if we can not find the command, check the environment
    if not os.path.lexists(commandAsList[0]) and find_executable(str(commandAsList[0]), str(pathEnvironment)):
        commandAsList[0] = find_executable(str(commandAsList[0]), str(pathEnvironment))

    if currentWorkingDirectory and not os.path.lexists(currentWorkingDirectory):
        os.makedirs(currentWorkingDirectory)

    print(os.linesep + '========================== do ... ==========================')
    if currentWorkingDirectory:
        print("Working Directory: " + currentWorkingDirectory)
    else:
        print("No currentWorkingDirectory set!")
    print("Last command:      " + ' '.join(commandAsList))
    sys.stdout.flush()

    if currentWorkingDirectory and not os.path.lexists(currentWorkingDirectory):
        raise Exception("The current working directory is not existing: %s" % currentWorkingDirectory)

    useShell = True if sys.platform.startswith('win') else False
    lastStdOutLines = []
    lastStdErrLines = []
    if currentThread().name == "MainThread" and not onlyErrorCaseOutput:
        process = Popen(
            commandAsList, shell=useShell,
            cwd=currentWorkingDirectory, bufsize=-1, env=environment
        )
    else:
        process = Popen(
            commandAsList, shell=useShell,
            stdout=PIPE, stderr=PIPE,
            cwd=currentWorkingDirectory, bufsize=-1, env=environment
        )

        maxSavedLineNumbers = 1000
        lastStdOutLines = deque(maxlen=maxSavedLineNumbers)
        lastStdErrLines = deque(maxlen=maxSavedLineNumbers)

        # Launch the asynchronous readers of the process' stdout and stderr.
        stdout = AsynchronousFileReader(process.stdout)
        stderr = AsynchronousFileReader(process.stderr)

        # Check the readers if we received some output (until there is nothing more to get).
        while not stdout.eof() or not stderr.eof():
            # Show what we received from standard output.
            for line in stdout.readlines():
                line = line.decode()
                lastStdOutLines.append(line)
                if currentThread().name != "MainThread":
                    sys.stdout.write(line)

            # Show what we received from standard error.
            for line in stderr.readlines():
                line = line.decode()
                lastStdErrLines.append(line)
                if currentThread().name != "MainThread":
                    sys.stdout.write(line)

            # Sleep a bit before polling the readers again.
            sleep(1)

        # Let's be tidy and join the threads we've started.
        stdout.join()
        stderr.join()

        # Close subprocess' file descriptors.
        process.stdout.close()
        process.stderr.close()

    process.wait()
    exitCode = process.returncode

    # lets keep that for debugging
    # if environment:
    #     for key in sorted(environment):
    #         sys.stderr.write("set " + key + "=" + environment[key] + os.linesep)
    if exitCode not in expectedExitCodes:
        lastOutput = ""
        exit_type = ""
        if currentThread().name != "MainThread" or onlyErrorCaseOutput:
            if len(lastStdErrLines) != 0:
                lastOutput += "".join(str(lastStdErrLines))
                exit_type = "error "
            elif len(lastStdOutLines) != 0:
                lastOutput += "".join(str(lastStdOutLines))
        prettyLastOutput = os.linesep + '======================= error =======================' + os.linesep
        prettyLastOutput += "Working Directory: " + currentWorkingDirectory + os.linesep
        prettyLastOutput += "Last command:      " + ' '.join(commandAsList) + os.linesep
        if lastOutput:
            prettyLastOutput += "last {0}output:{1}{2}".format(exit_type, os.linesep, lastOutput)
        else:
            prettyLastOutput += " - no process output caught - "
        raise Exception("Different exit code then expected({0}): {1}{2}".format(expectedExitCodes, exitCode, prettyLastOutput))
    return exitCode


@deep_copy_arguments
def runInstallCommand(arguments=['install'], currentWorkingDirectory=None, callerArguments=None, extra_environment=None, onlyErrorCaseOutput=False):
    if hasattr(callerArguments, 'installcommand') and callerArguments.installcommand:
        installcommand = callerArguments.installcommand.split()
    else:
        installcommand = ['make', '-j1']
        # had the case that the -j1 on the make command was ignored if there is a MAKEFLAGS variable
        if os.name != 'nt':
            if extra_environment is None:
                extra_environment = {}
            extra_environment["MAKEFLAGS"] = "-j1"

    if arguments:
        installcommand.extend(arguments if type(arguments) is list else arguments.split())
    return runCommand(installcommand, currentWorkingDirectory, callerArguments, extra_environment=extra_environment, onlyErrorCaseOutput=onlyErrorCaseOutput)


@deep_copy_arguments
def runBuildCommand(arguments=None, currentWorkingDirectory=None, callerArguments=None, extra_environment=None, onlyErrorCaseOutput=False, expectedExitCodes=[0]):
    buildcommand = ['make']
    if hasattr(callerArguments, 'buildcommand') and callerArguments.buildcommand:
        buildcommand = callerArguments.buildcommand.split()

    if arguments:
        buildcommand.extend(arguments if type(arguments) is list else arguments.split())
    return runCommand(buildcommand, currentWorkingDirectory, callerArguments, extra_environment=extra_environment, onlyErrorCaseOutput=onlyErrorCaseOutput, expectedExitCodes=expectedExitCodes)


@deep_copy_arguments
def getReturnValue(command, currentWorkingDirectory=None, extra_environment=None, callerArguments=None):
    commandAsList = command[:].split(' ')
    return Popen(
        commandAsList, stdout=PIPE, stderr=STDOUT,
        cwd=currentWorkingDirectory, env=getEnvironment(extra_environment, callerArguments)
    ).communicate()[0].strip()


def gitSHA(path, callerArguments=None):
    gitBinary = "git"
    if isGitDirectory(path):
        return getReturnValue(gitBinary + " rev-list -n1 HEAD", currentWorkingDirectory=path, callerArguments=callerArguments).strip()
    return ''


# get commit SHA either directly from git, or from a .tag file in the source directory
def get_commit_SHA(source_path, callerArguments=None):
    buildGitSHA = gitSHA(source_path, callerArguments)
    if not buildGitSHA:
        tagfile = os.path.join(source_path, '.tag')
        if os.path.exists(tagfile):
            with open(tagfile, 'r') as f:
                buildGitSHA = f.read().strip()
    return buildGitSHA


def isGitDirectory(repository_path):
    if not repository_path:
        return False
    gitConfigDir = os.path.abspath(os.path.join(repository_path, '.git'))
    return os.path.lexists(gitConfigDir)


def file_url(file_path):
    return urljoin('file:', pathname2url(file_path))
