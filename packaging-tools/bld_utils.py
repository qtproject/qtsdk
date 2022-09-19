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

import os
import shutil
import sys
from argparse import Namespace
from builtins import OSError
from collections import deque
from copy import deepcopy
from pathlib import Path
from socket import setdefaulttimeout
from subprocess import PIPE, STDOUT, Popen
from sys import platform
from threading import current_thread
from time import sleep
from typing import Any, Dict, List, Optional, Union
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse
from urllib.request import pathname2url, urlopen

# 3rd party module to read process output in a convenient way
from asynchronousfilereader import AsynchronousFileReader
from logging_util import init_logger

log = init_logger(__name__, debug_mode=False)

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
def deep_copy_arguments(to_call: Any) -> Any:
    def func(*args: Any, **kwargs: Any) -> Any:
        return to_call(*(deepcopy(x) for x in args),
                       **{k: deepcopy(v) for k, v in kwargs.items()})
    return func


class DirRenamer():

    def __init__(self, path: str, new_name: str) -> None:
        self.old_name = Path(path)
        self.new_name = Path(path).with_name(new_name)
        log.info("self.old_name: %s", self.old_name)
        log.info("self.new_name: %s", self.new_name)

    def __enter__(self) -> None:
        if self.old_name != self.new_name:
            self.old_name.rename(self.new_name)

    def __exit__(self, etype: Any, value: Any, etraceback: Any) -> None:
        if self.old_name != self.new_name:
            self.new_name.rename(self.old_name)


def compress(path: str, directory_name: str, sevenzip_target: str) -> None:
    sevenzip_extension = os.extsep + '7z'
    sevenzip_target_path = Path(sevenzip_target)
    parent_directory_path = os.path.abspath(os.path.join(path, '..'))
    if sevenzip_target_path.suffix != sevenzip_extension:
        sevenzip_target_path.with_suffix(sevenzip_extension)
    sevenzip_filename = sevenzip_target_path.name
    with DirRenamer(path, directory_name):
        run_command(' '.join(('7z a -mx9', sevenzip_filename, directory_name)), parent_directory_path)

    current_sevenzip_path = Path(parent_directory_path, sevenzip_filename)
    if current_sevenzip_path != sevenzip_target_path:
        shutil.move(current_sevenzip_path, sevenzip_target_path)


def strip_vars(sobject: Namespace, chars: str) -> None:
    for key, value in vars(sobject).items():
        if isinstance(value, str):
            setattr(sobject, key, value.strip(chars))


def urllib2_response_read(response: Any, file_path: str, block_size: int, total_size: int) -> int:
    total_size = int(total_size)
    bytes_count: int = 0

    with open(file_path, "wb") as filename:
        old_percent: float = -1
        while 1:
            block = response.read(block_size)
            filename.write(block)
            bytes_count += len(block)

            if not block:
                break

            percent = min(100, bytes_count * 100 / total_size)
            if percent != old_percent:
                sys.stdout.write(f"\r{percent}%")
            old_percent = percent

    return bytes_count


def download(url: str, target: str, read_block_size: int = 1048576) -> None:
    try:
        if os.path.isdir(os.path.abspath(target)):
            filename = Path(urlparse(url).path).name
            target = os.path.join(os.path.abspath(target), filename)
        if os.path.lexists(target):
            raise Exception(f"Can not download '{url}' to '{target}' as target. The file already exists.")

        def local_download(local_file_path: str, target_file_path: str) -> None:
            if os.path.isfile(local_file_path):
                log.info("copying file from '%s' to '%s'", local_file_path, target_file_path)
                try:
                    os.makedirs(os.path.dirname(target_file_path))
                except Exception:
                    pass
                shutil.copy2(local_file_path, target)
                log.info("Done")

        if os.path.lexists(url[len("file:///"):]):
            # because scheme of a absolute windows path is the drive letter in python 2,
            # we need to use file:// as a work around in urls
            local_download(url[len("file:///"):], target)
            return
        # there is code which only have two slashes - protocol://host/path <- localhost can be omitted
        if os.path.lexists(url[len("file://"):]):
            local_download(url[len("file://"):], target)
            return
        if os.path.lexists(url):
            local_download(url, target)
            return

        savefile_tmp = os.extsep.join((target, 'tmp'))
        try:
            os.makedirs(os.path.dirname(savefile_tmp))
        except Exception:
            pass

        try:
            # use urlopen which raise an error if that file is not existing
            with urlopen(url) as response:
                total_size = response.info().get('Content-Length').strip()
                log.info("Download file from '%s' sized %s bytes to %s", url, total_size, target)
                # run the download
                received_size = urllib2_response_read(response, savefile_tmp, read_block_size, total_size)
            if received_size != int(total_size):
                raise Exception(f"Broken download, got a wrong size after download from '{url}'(total size: {total_size}, but {received_size} received).")
        except HTTPError as error:
            raise Exception(f"Can not download '{url}' to '{target}' as target(error code: '{error.code}').") from error

        renamed = False
        try_rename_counter = 0
        while renamed is False :
            try_rename_counter = try_rename_counter + 1
            try:
                if try_rename_counter > 5 :
                    sys.stdout.write(f"r{try_rename_counter}")
                if os.path.lexists(target):
                    raise Exception(f"Please remove savefile first: {target}")
                os.rename(savefile_tmp, target)
                if not os.path.lexists(savefile_tmp):
                    renamed = True
                    # make sure that another output starts in a new line
                    sys.stdout.write(os.linesep)
            except OSError as error:
                # if it still exists just try that after a microsleep and stop this after 720 tries
                if os.path.lexists(savefile_tmp) and try_rename_counter < 720:
                    sleep(2)
                    continue
                if not os.path.lexists(target):
                    raise Exception(f"Could not rename {savefile_tmp} to {target}{os.linesep}Error: {str(error)}") from error
    finally:  # this is done before the except code is called
        try:
            os.remove(savefile_tmp)
        except Exception:  # swallow, do not shadow actual error
            pass


def set_value_on_environment_dict(environment: Dict[str, str], key: str, value: str) -> None:
    if key in environment:
        # if the data already contains the value stop here
        if value in environment[key].split(os.pathsep):
            return
        environment[key] = os.pathsep.join((value, environment[key]))
    else:
        environment[key] = value


@deep_copy_arguments
def get_environment(extra_environment: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    # first take the one from the system and use the plain dictionary data for that
    environment = dict(os.environ)

    if not extra_environment:
        return environment

    for key in extra_environment.keys():
        key_upper = key.upper()
        if any((key_upper == 'PATH', key_upper == 'INCLUDE', key_upper == 'LIB')):
            set_value_on_environment_dict(environment, key, extra_environment[key])
        else:
            environment[key] = extra_environment[key]
    return environment


@deep_copy_arguments
def run_command(command: Union[List[str], str], cwd: str, extra_environment: Optional[Dict[str, str]] = None, only_error_case_output: bool = False, expected_exit_codes: Optional[List[int]] = None) -> int:
    expected_exit_codes = expected_exit_codes or [0]

    if isinstance(command, list):
        command_as_list = command
    else:
        command_as_list = command[:].split(' ')

    environment = get_environment(extra_environment)

    # if we can not find the command, just check the current working dir
    if (not os.path.lexists(command_as_list[0]) and cwd
            and os.path.isfile(os.path.abspath(os.path.join(cwd, command_as_list[0])))):
        command_as_list[0] = os.path.abspath(os.path.join(cwd, command_as_list[0]))

    path_environment = environment['PATH']
    # if we can not find the command, check the environment
    found_executable = shutil.which(str(command_as_list[0]), path=str(path_environment))
    if not os.path.lexists(command_as_list[0]) and found_executable:
        command_as_list[0] = found_executable

    if cwd and not os.path.lexists(cwd):
        os.makedirs(cwd)

    log.info("========================== do ... ==========================")
    if cwd:
        log.info("Working Directory: %s", cwd)
    else:
        log.warning("No cwd set!")
    log.info("Last command: %s", " ".join(command_as_list))
    sys.stdout.flush()

    if cwd and not os.path.lexists(cwd):
        raise Exception(f"The current working directory is not existing: {cwd}")

    use_shell = is_windows()
    last_stdout_lines: List[Any] = []
    last_stderr_lines: List[Any] = []
    if current_thread().name == "MainThread" and not only_error_case_output:
        process = Popen(
            command_as_list, shell=use_shell,
            cwd=cwd, bufsize=-1, env=environment
        )
    else:
        process = Popen(  # pylint: disable=R1732
            command_as_list, shell=use_shell,
            stdout=PIPE, stderr=PIPE,
            cwd=cwd, bufsize=-1, env=environment
        )

        max_saved_line_numbers = 1000
        last_stdout_lines = list(deque(maxlen=max_saved_line_numbers))
        last_stderr_lines = list(deque(maxlen=max_saved_line_numbers))

        # Launch the asynchronous readers of the process' stdout and stderr.
        stdout = AsynchronousFileReader(process.stdout)
        stderr = AsynchronousFileReader(process.stderr)

        # Check the readers if we received some output (until there is nothing more to get).
        while not stdout.eof() or not stderr.eof():
            # Show what we received from standard output.
            for line in stdout.readlines():
                line = line.decode()
                last_stdout_lines.append(line)
                if current_thread().name != "MainThread":
                    sys.stdout.write(line)

            # Show what we received from standard error.
            for line in stderr.readlines():
                line = line.decode()
                last_stderr_lines.append(line)
                if current_thread().name != "MainThread":
                    sys.stdout.write(line)

            # Sleep a bit before polling the readers again.
            sleep(1)

        # Let's be tidy and join the threads we've started.
        stdout.join()
        stderr.join()

        # Close subprocess' file descriptors.
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()

    process.wait()
    exit_code = process.returncode

    # lets keep that for debugging
    # if environment:
    #     for key in sorted(environment):
    #         sys.stderr.write("set " + key + "=" + environment[key] + os.linesep)
    if exit_code not in expected_exit_codes:
        last_output = ""
        exit_type = ""
        if current_thread().name != "MainThread" or only_error_case_output:
            if len(last_stderr_lines) != 0:
                last_output += "".join(str(last_stderr_lines))
                exit_type = "error "
            elif len(last_stdout_lines) != 0:
                last_output += "".join(str(last_stdout_lines))
        pretty_last_output = os.linesep + '======================= error =======================' + os.linesep
        pretty_last_output += "Working Directory: " + cwd + os.linesep
        pretty_last_output += "Last command:      " + ' '.join(command_as_list) + os.linesep
        if last_output:
            pretty_last_output += f"last {exit_type}output:{os.linesep}{last_output}"
        else:
            pretty_last_output += " - no process output caught - "
        raise Exception(f"Different exit code then expected({expected_exit_codes}): {exit_code}{pretty_last_output}")
    return exit_code


@deep_copy_arguments
def run_install_command(
    arguments: Optional[List[str]] = None,
    cwd: Optional[str] = None,
    caller_arguments: Optional[Namespace] = None,
    extra_environment: Optional[Dict[str, str]] = None,
    only_error_case_output: bool = False,
) -> str:
    arguments = arguments or ['install']
    if caller_arguments and hasattr(caller_arguments, 'installcommand') and caller_arguments.installcommand:
        installcommand = caller_arguments.installcommand.split()
    else:
        installcommand = ['make', '-j1']
        # had the case that the -j1 on the make command was ignored if there is a MAKEFLAGS variable
        if os.name != 'nt':
            if extra_environment is None:
                extra_environment = {}
            extra_environment["MAKEFLAGS"] = "-j1"

    if arguments:
        installcommand.extend(arguments)
    return str(run_command(installcommand, cwd, extra_environment, only_error_case_output=only_error_case_output))


@deep_copy_arguments
def run_build_command(
    arguments: Optional[List[str]] = None,
    cwd: Optional[str] = None,
    caller_arguments: Optional[Namespace] = None,
    extra_environment: Optional[Dict[str, str]] = None,
    only_error_case_output: bool = False,
    expected_exit_codes: Optional[List[int]] = None,
) -> str:
    expected_exit_codes = expected_exit_codes or [0]
    buildcommand = ['make']
    if caller_arguments and hasattr(caller_arguments, 'buildcommand') and caller_arguments.buildcommand:
        buildcommand = caller_arguments.buildcommand.split()

    if arguments:
        buildcommand.extend(arguments)
    return str(run_command(buildcommand, cwd, extra_environment, only_error_case_output=only_error_case_output, expected_exit_codes=expected_exit_codes))


@deep_copy_arguments
def get_return_value(
    command: str, cwd: Optional[str] = None, extra_environment: Optional[Dict[str, str]] = None
) -> bytes:
    command_as_list = command[:].split(' ')
    return Popen(
        command_as_list, stdout=PIPE, stderr=STDOUT,
        cwd=cwd, env=get_environment(extra_environment)
    ).communicate()[0].strip()


def git_sha(path: str) -> str:
    git_binary = "git"
    if is_git_directory(path):
        return str(get_return_value(git_binary + " rev-list -n1 HEAD", cwd=path).strip())
    return ''


# get commit SHA either directly from git, or from a .tag file in the source directory
def get_commit_sha(source_path: str) -> str:
    build_git_sha = git_sha(source_path)
    if not build_git_sha:
        tagfile = os.path.join(source_path, '.tag')
        if os.path.exists(tagfile):
            with open(tagfile, 'r', encoding="utf-8") as handle:
                build_git_sha = handle.read().strip()
    return build_git_sha


def is_git_directory(repository_path: str) -> bool:
    if not repository_path:
        return False
    git_config_dir = os.path.abspath(os.path.join(repository_path, '.git'))
    return os.path.lexists(git_config_dir)


def file_url(file_path: str) -> str:
    return urljoin('file:', pathname2url(file_path))
