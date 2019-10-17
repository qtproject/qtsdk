#!/usr/bin/env python
#############################################################################
##
## Copyright (C) 2013 Digia Plc and/or its subsidiary(-ies).
## Contact: http://www.qt-project.org/legal
##
## This file is part of the release tools of the Qt Toolkit.
##
## $QT_BEGIN_LICENSE:LGPL$
## Commercial License Usage
## Licensees holding valid commercial Qt licenses may use this file in
## accordance with the commercial license agreement provided with the
## Software or, alternatively, in accordance with the terms contained in
## a written agreement between you and Digia.  For licensing terms and
## conditions see http://qt.digia.com/licensing.  For further information
## use the contact form at http://qt.digia.com/contact-us.
##
## GNU Lesser General Public License Usage
## Alternatively, this file may be used under the terms of the GNU Lesser
## General Public License version 2.1 as published by the Free Software
## Foundation and appearing in the file LICENSE.LGPL included in the
## packaging of this file.  Please review the following information to
## ensure the GNU Lesser General Public License version 2.1 requirements
## will be met: http://www.gnu.org/licenses/old-licenses/lgpl-2.1.html.
##
## In addition, as a special exception, Digia gives you certain additional
## rights.  These rights are described in the Digia Qt LGPL Exception
## version 1.1, included in the file LGPL_EXCEPTION.txt in this package.
##
## GNU General Public License Usage
## Alternatively, this file may be used under the terms of the GNU
## General Public License version 3.0 as published by the Free Software
## Foundation and appearing in the file LICENSE.GPL included in the
## packaging of this file.  Please review the following information to
## ensure the GNU General Public License version 3.0 requirements will be
## met: http://www.gnu.org/copyleft/gpl.html.
##
##
## $QT_END_LICENSE$
##
#############################################################################

# import the print function which is used in python 3.x
from __future__ import print_function

# built in imports
from distutils.spawn import find_executable # runCommand method
import os
import sys
import time
import urllib2
import shutil
import subprocess
import threading
import collections
import urlparse
import urllib

#fix that there was var with name "type" in a calling test for runCommand when trying
#to use __builtin__.type()
import __builtin__

# 3rd party module to read process output in a convenient way
from asynchronousfilereader import AsynchronousFileReader

# own imports
import environmentfrombatchfile

# make a timeout for download jobs
import socket
socket.setdefaulttimeout(30)

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
    with DirRenamer(path, directoryName) as otherThing:
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

def download(url, target, read_block_size = 1048576):
    try:
        if os.path.isdir(os.path.abspath(target)):
            filename = os.path.basename(urlparse.urlparse(url).path)
            target = os.path.join(os.path.abspath(target), filename)
        if os.path.lexists(target):
            raise Exception("Can not download '{0}' to '{1}' as target. The file already exists.".format(url, target))
        # now a download can be a local path
        if url.startswith("file://"):
            # because scheme of a absolute windows path is the drive letter in python 2,
            # we need to use file:// as a work around in urls
            url = url[len("file://"):]
        if os.path.lexists(url) and os.path.isfile(url):
            print("copying file from '{0}' to {1}".format(url, target))
            try:
                os.makedirs(os.path.dirname(target))
            except:
                pass
            shutil.copy2(url, target)
            print("Done" + os.linesep)
            return

        savefile_tmp = os.extsep.join((target, 'tmp'))
        try:
            os.makedirs(os.path.dirname(savefile_tmp))
        except:
            pass

        try:
            # use urlopen which raise an error if that file is not existing
            response = urllib2.urlopen(url)
            total_size = response.info().getheader('Content-Length').strip()
            print("Downloading file from '{0}' with size {1} bytes to {2}".format(url, total_size, target))
            # run the download
            received_size = urllib2_response_read(response, savefile_tmp, read_block_size, total_size)
            if received_size != int(total_size):
                raise Exception("Broken download, got a wrong size after download from '{0}'(total size: {1}, but {2} received).".format(url, total_size, received_size))
        except urllib2.HTTPError, error:
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
            except WindowsError as e:
                # if it still exists just try that after a microsleep and stop this after 720 tries
                if os.path.lexists(savefile_tmp) and tryRenameCounter < 720:
                    time.sleep(2)
                    continue
                else:
                    if not os.path.lexists(target):
                        raise Exception("Could not rename {0} to {1}{2}Error: {3}".format(savefile_tmp, target, os.linesep, e.message))
    finally: # this is done before the except code is called
        try:
            os.remove(savefile_tmp)
        except: #swallow, do not shadow actual error
            pass

def setValueOnEnvironmentDict(environment, key, value):
    # convert PATH to Path to avoid duplicates
    if os.name == 'nt' and key == 'PATH':
        key = 'Path'

    if key in environment:
        # if the data already contains the value stop here
        if value in environment[key].split(os.pathsep):
            return
        environment[key] = os.pathsep.join((value, environment[key]))
    else:
        environment[key] = value

def getEnvironment(init_environment = None, callerArguments = None):
    if init_environment is None:
        init_environment = {}
    # first take the one from the system and use the plain dictionary data for that
    environment = os.environ.__dict__["data"]

    if hasattr(callerArguments, 'environment_batch') and callerArguments.environment_batch:
        environment = environmentfrombatchfile.get(
            callerArguments.environment_batch, arguments = callerArguments.environment_batch_argument)

    if (hasattr(callerArguments, 'gnuwin32binpath') and callerArguments.gnuwin32binpath and
        os.path.lexists(callerArguments.gnuwin32binpath)):
        setValueOnEnvironmentDict(environment, 'PATH', callerArguments.gnuwin32binpath)

    if hasattr(callerArguments, 'pythonpath') and callerArguments.pythonpath:
        setValueOnEnvironmentDict(environment, 'PATH', callerArguments.pythonpath)
    if hasattr(callerArguments, 'perlpath') and callerArguments.perlpath:
        setValueOnEnvironmentDict(environment, 'PATH', callerArguments.perlpath)
    if hasattr(callerArguments, 'icupath') and callerArguments.icupath:
        setValueOnEnvironmentDict(environment, 'PATH', os.path.join(callerArguments.icupath, 'bin'))
        setValueOnEnvironmentDict(environment, 'INCLUDE', os.path.join(callerArguments.icupath, 'include'))
        setValueOnEnvironmentDict(environment, 'LIB', os.path.join(callerArguments.icupath, 'lib'))
    if hasattr(callerArguments, 'opensslpath') and callerArguments.opensslpath:
        setValueOnEnvironmentDict(environment, 'PATH', os.path.join(callerArguments.opensslpath, 'bin'))
        setValueOnEnvironmentDict(environment, 'INCLUDE', os.path.join(callerArguments.opensslpath, 'include'))
        setValueOnEnvironmentDict(environment, 'LIB', os.path.join(callerArguments.opensslpath, 'lib'))

    if not init_environment:
        return environment

    # if we have an init_environment we merge the environment dicts
    merged_environment = {}
    for key in init_environment.viewkeys():
        keyUpper = key.upper()
        if any((keyUpper == 'PATH', keyUpper == 'INCLUDE', keyUpper == 'LIB')):
            # use save setValueOnEnvironmentDict in case there are PATH and Path
            setValueOnEnvironmentDict(merged_environment, key, init_environment[key])
        else:
            merged_environment[key] = init_environment[key]
    # now add the ones from the system environment
    for key in environment.viewkeys():
        keyUpper = key.upper()
        if any((keyUpper == 'PATH', keyUpper == 'INCLUDE', keyUpper == 'LIB')):
            setValueOnEnvironmentDict(merged_environment, key, environment[key])
        else:
            merged_environment[key] = environment[key]
    return merged_environment


def runCommand(command, currentWorkingDirectory, callerArguments = None, init_environment = None, onlyErrorCaseOutput=False, expectedExitCodes=[0]):
    if __builtin__.type(expectedExitCodes) is not list:
        raise TypeError("{}({}) is not {}".format("expectedExitCodes", __builtin__.type(expectedExitCodes), list))
    if __builtin__.type(onlyErrorCaseOutput) is not bool:
        raise TypeError("{}({}) is not {}".format("onlyErrorCaseOutput", __builtin__.type(onlyErrorCaseOutput), bool))

    if __builtin__.type(command) is list:
        commandAsList = command
    else:
        commandAsList = command[:].split(' ')

    environment = getEnvironment(init_environment, callerArguments)

    # add some necessary paths
    if hasattr(callerArguments, 'gitpath') and callerArguments.gitpath and commandAsList[0] == 'git':
        commandAsList[0] = os.path.abspath(os.path.join(callerArguments.gitpath, 'git'))
    if hasattr(callerArguments, 'perlpath') and callerArguments.perlpath and commandAsList[0] == 'perl':
        commandAsList[0] = os.path.abspath(os.path.join(callerArguments.perlpath, 'perl'))
    if hasattr(callerArguments, 'sevenzippath') and callerArguments.sevenzippath and commandAsList[0] == '7z':
        commandAsList[0] = os.path.abspath(os.path.join(callerArguments.sevenzippath, '7z'))

    # if we can not find the command, just check the current working dir
    if not os.path.lexists(commandAsList[0]) and currentWorkingDirectory and \
        os.path.isfile(os.path.abspath(os.path.join(currentWorkingDirectory, commandAsList[0]))):
        commandAsList[0] = os.path.abspath(os.path.join(currentWorkingDirectory, commandAsList[0]))

    if 'Path' in environment:
        pathEnvironment = environment['Path']
    elif 'PATH' in environment:
        pathEnvironment = environment['PATH']
    # if we can not find the command, check the environment
    if not os.path.lexists(commandAsList[0]) and find_executable(commandAsList[0], pathEnvironment):
        commandAsList[0] = find_executable(commandAsList[0], pathEnvironment)

    if currentWorkingDirectory and not os.path.lexists(currentWorkingDirectory):
        os.makedirs(currentWorkingDirectory)

    print(os.linesep + '========================== do ... ==========================')
    if currentWorkingDirectory:
        print("Working Directory: " + currentWorkingDirectory)
    else:
        print("No currentWorkingDirectory set!")
    print("Last command:      " + ' '.join(commandAsList))

    if currentWorkingDirectory and not os.path.lexists(currentWorkingDirectory):
        raise Exception("The current working directory is not existing: %s" % currentWorkingDirectory)

    useShell = True if sys.platform.startswith('win') else False
    lastStdOutLines = []
    lastStdErrLines = []
    if threading.currentThread().name == "MainThread" and not onlyErrorCaseOutput:
        process = subprocess.Popen(commandAsList, shell=useShell,
            cwd = currentWorkingDirectory, bufsize = -1, env = environment)
    else:
        process = subprocess.Popen(commandAsList, shell=useShell,
            stdout = subprocess.PIPE, stderr = subprocess.PIPE,
            cwd = currentWorkingDirectory, bufsize = -1, env = environment)

        maxSavedLineNumbers = 100
        lastStdOutLines = collections.deque(maxlen = maxSavedLineNumbers)
        lastStdErrLines = collections.deque(maxlen = maxSavedLineNumbers)

        # Launch the asynchronous readers of the process' stdout and stderr.
        stdout = AsynchronousFileReader(process.stdout)
        stderr = AsynchronousFileReader(process.stderr)

        # Check the readers if we received some output (until there is nothing more to get).
        while not stdout.eof() or not stderr.eof():
            # Show what we received from standard output.
            for line in stdout.readlines():
                lastStdOutLines.append(line)
                if threading.currentThread().name != "MainThread":
                    sys.stdout.write(line)

            # Show what we received from standard error.
            for line in stderr.readlines():
                lastStdErrLines.append(line)
                if threading.currentThread().name != "MainThread":
                    sys.stdout.write(line)

            # Sleep a bit before polling the readers again.
            time.sleep(1)

        # Let's be tidy and join the threads we've started.
        stdout.join()
        stderr.join()

        # Close subprocess' file descriptors.
        process.stdout.close()
        process.stderr.close()

    process.wait()
    exitCode = process.returncode

    # lets keep that for debugging
    #if environment:
    #    for key in sorted(environment):
    #        sys.stderr.write("set " + key + "=" + environment[key] + os.linesep)
    if exitCode not in expectedExitCodes:
        lastOutput = ""
        type = ""
        if threading.currentThread().name != "MainThread" or onlyErrorCaseOutput:
            if len(lastStdErrLines) != 0:
                lastOutput += "".join(lastStdErrLines)
                type = "error "
            elif len(lastStdOutLines) != 0:
                lastOutput += "".join(lastStdOutLines)
        prettyLastOutput = os.linesep + '======================= error =======================' + os.linesep
        prettyLastOutput += "Working Directory: " + currentWorkingDirectory + os.linesep
        prettyLastOutput += "Last command:      " + ' '.join(commandAsList) + os.linesep
        if lastOutput:
            prettyLastOutput += "last {0}output:{1}{2}".format(type, os.linesep, lastOutput)
        else:
            prettyLastOutput += " - no process output caught - "
        raise Exception("Different exit code then expected({0}): {1}{2}".format(expectedExitCodes, exitCode, prettyLastOutput))
    return exitCode

def runInstallCommand(arguments = ['install'], currentWorkingDirectory = None, callerArguments = None, init_environment = None):
    if init_environment is None:
        init_environment = {}
    if hasattr(callerArguments, 'installcommand') and callerArguments.installcommand:
        installcommand = callerArguments.installcommand.split()
    else:
        installcommand = ['make', '-j1']
        # had the case that the -j1 on the make command was ignored if there is a MAKEFLAGS variable
        if os.name != 'nt':
            init_environment["MAKEFLAGS"] = "-j1"

    if arguments:
        installcommand.extend(arguments if __builtin__.type(arguments) is list else arguments.split())
    return runCommand(installcommand, currentWorkingDirectory, callerArguments, init_environment = init_environment)

def runBuildCommand(arguments = None, currentWorkingDirectory = None, callerArguments = None, init_environment = None):
    if init_environment is None:
        init_environment = {}
    buildcommand = ['make']
    if hasattr(callerArguments, 'buildcommand') and callerArguments.buildcommand:
        buildcommand = callerArguments.buildcommand.split()

    if arguments:
        buildcommand.extend(arguments if __builtin__.type(arguments) is list else arguments.split())
    return runCommand(buildcommand, currentWorkingDirectory, callerArguments, init_environment = init_environment)

def getReturnValue(command, currentWorkingDirectory = None, init_environment = None, callerArguments = None):
    if init_environment is None:
        init_environment = {}
    commandAsList = command[:].split(' ')
    return subprocess.Popen(commandAsList, stdout=subprocess.PIPE, stderr = subprocess.STDOUT,
        cwd = currentWorkingDirectory, env = getEnvironment(init_environment, callerArguments)).communicate()[0].strip()

def gitSHA(path, callerArguments = None):
    gitBinary = "git"
    if hasattr(callerArguments, 'gitpath') and callerArguments.gitpath:
        gitBinary = os.path.abspath(os.path.join(callerArguments.gitpath, 'git'))
    if isGitDirectory(path):
        return getReturnValue(gitBinary + " rev-list -n1 HEAD", currentWorkingDirectory = path, callerArguments = callerArguments).strip()
    return ''

def isGitDirectory(repository_path):
    if not repository_path:
        return False
    gitConfigDir = os.path.abspath(os.path.join(repository_path, '.git'))
    return os.path.lexists(gitConfigDir)

def file_url(file_path):
    return urlparse.urljoin('file:', urllib.pathname2url(file_path))
