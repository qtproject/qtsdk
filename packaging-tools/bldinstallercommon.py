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

import ctypes
import errno
import itertools
import os
import re
import shutil
import stat
import sys
from argparse import Namespace
from configparser import ConfigParser
from contextlib import suppress
from fnmatch import fnmatch
from pathlib import Path
from subprocess import CalledProcessError
from traceback import print_exc
from types import TracebackType
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse
from urllib.request import url2pathname, urlcleanup, urlretrieve

import requests
from temppathlib import TemporaryDirectory

from bld_utils import download, is_linux, is_macos, is_windows, run_command
from installer_utils import PackagingError
from logging_util import init_logger
from runner import run_cmd
from threadedwork import Task, ThreadedWork

log = init_logger(__name__, debug_mode=False)

MAX_DEBUG_PRINT_LENGTH = 10000


def is_long_path_supported() -> bool:
    """
    Check whether long paths (~260+) are supported by the current environment

    On Windows, the limitations can be removed via Group Policy or Registry Key
    For more information on Windows API maximum path length limitations, see:
    https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation

    Returns:
        bool: whether the current process environment has path limitation disabled (Windows)
        True: non-Windows platforms
    """
    if not is_windows():
        return True
    ntdll = ctypes.WinDLL('ntdll')  # type: ignore  # false positive mypy
    if not hasattr(ntdll, 'RtlAreLongPathsEnabled'):
        return False
    ntdll.RtlAreLongPathsEnabled.restype = ctypes.c_ubyte
    ntdll.RtlAreLongPathsEnabled.argtypes = ()
    return bool(ntdll.RtlAreLongPathsEnabled())


def file_uri_to_path(uri: str) -> Path:
    """
    Convert file:// uris and string paths to pathlib path

    Examples:
        # unix
        file:///home/qt/foo%20bar -> Path("/home/qt/foo bar")
        # windows
        file:///c:/users/qt/foo%20bar -> Path("c:/users/qt/foo bar")
        # string path
        c:\\users\\qt\\foo\\bar -> Path("c:\\users\\qt\\foo\\bar")

    Args:
        uri: A string containing a file:// uri or path

    Returns:
        A pathlib.Path object
    """
    if uri.startswith("file://"):
        uri = url2pathname(uri.replace("file://", ""))
    return Path(uri)


def uri_exists(uri: str) -> bool:
    """
    Check URI and return whether the location exists, log the errors if any
    HTTP URLs will be validated using the response headers from a HEAD request
    Timeout for remote requests is set to 30 seconds

    Args:
        uri: An URI pointing to a local file or a remote file (HTTP)

    Returns:
        True if the file exists at the given URI location, otherwise False
    """
    # check first if the url points to file on local file system (i.e. not http)
    if not uri.startswith(("http://", "https://")):
        # convert file URI to pathname
        return file_uri_to_path(uri).resolve().is_file()
    try:
        with requests.head(uri, timeout=30, stream=True) as res:
            res.raise_for_status()
            if int(res.headers["content-length"]) > 0:
                return True
            log.error("Invalid content length: %s", res.headers['content-length'])
    except requests.exceptions.HTTPError as err:  # HTTP error status codes
        log.exception("HTTP %s: %s", err.response.status_code, err.response.text)
    except requests.exceptions.RequestException as err:  # Other errors
        log.exception("Error while checking URI: %s", str(err))
    return False


###############################
# function
###############################
def dl_progress(count: int, block_size: int, total_size: int) -> None:
    current_download_percent = 0
    percent = int(count * block_size * 100 / total_size)
    # produce only reasonable amount of prints into stdout
    if percent > current_download_percent:
        current_download_percent = percent
        sys.stdout.write("\r" + f"     Downloading: {percent}%")
        sys.stdout.flush()
    if count * block_size >= total_size:
        current_download_percent = 0
        sys.stdout.write("\n")


###############################
# function
###############################
def retrieve_url(url: str, savefile: str) -> None:
    savefile_tmp: str = ""
    try:
        savefile_tmp = savefile + '.tmp'
        urlcleanup()
        urlretrieve(url, savefile_tmp, reporthook=dl_progress)
        shutil.move(savefile_tmp, savefile)
    except Exception as err:
        exc = sys.exc_info()[0]
        log.error(exc)
        try:
            os.remove(savefile_tmp)
        except Exception:  # swallow, do not shadow actual error
            pass
        raise Exception(exc) from err


###############################
# function
###############################
def search_for_files(
    search_path: Union[str, Path], suffixes: List[str], rgx_pattern: str
) -> List[str]:
    pattern = re.compile(rgx_pattern, flags=re.MULTILINE)

    def _matches_rgx(path: Path) -> bool:
        if rgx_pattern:
            with open(path, 'r', encoding="utf-8") as handle:
                return bool(pattern.search(handle.read()))
        return True
    return locate_paths(search_path, suffixes, filters=[os.path.isfile, _matches_rgx])


###############################
# function
###############################
def move_tree(srcdir: str, dstdir: str, pattern: Optional[str] = None) -> None:
    # dstdir must exist first
    srcnames = os.listdir(srcdir)
    for name in srcnames:
        srcfname = os.path.join(srcdir, name)
        if not srcfname:
            raise IOError('*** Fatal error! Unable to create source file path, too long path name!')
        dstfname = os.path.join(dstdir, name)
        if not dstfname:
            raise IOError('*** Fatal error! Unable to create destination file path, too long path name!')
        if os.path.isdir(srcfname) and not os.path.islink(srcfname):
            Path(dstfname).mkdir(parents=True, exist_ok=True)
            move_tree(srcfname, dstfname)
        elif pattern is None or fnmatch(name, pattern):
            if os.path.islink(srcfname):  # shutil.move fails moving directory symlinks over file system bounds...
                linkto = os.readlink(srcfname)
                os.symlink(linkto, dstfname)
                os.remove(srcfname)
            else:
                shutil.move(srcfname, dstfname)


###############################
# function
###############################
def copy_tree(source_dir: str, dest_dir: str) -> None:
    src_files = os.listdir(source_dir)
    for file_name in src_files:
        full_file_name = os.path.join(source_dir, file_name)
        if not full_file_name:
            raise IOError('*** Fatal error! Unable to create source file path, too long path name!')
        if is_windows():
            if len(full_file_name) > 255:
                raise IOError(f'given full_file_name length [{len(full_file_name)}] too long for Windows: {full_file_name}')
        if os.path.isdir(full_file_name):
            Path(dest_dir + os.sep + file_name).mkdir(parents=True, exist_ok=True)
            copy_tree(full_file_name, dest_dir + os.sep + file_name)
        if os.path.isfile(full_file_name):
            shutil.copy(full_file_name, dest_dir)


def strip_dirs(directory: Path, iterations: int = 1) -> None:
    """
    Remove unnecessary tree structure from a given directory path

    Args:
        directory: A file system path to the folder to strip from
        iterations: A number of middle directories to remove (0=do nothing)

    Raises:
        IOError: When the directory contains more than one subdirectory
        IOError: When the directory contains a non-directory
        IOError: When the directory contains no items
    """
    if not iterations:
        # if no directories to strip, do nothing
        return
    log.info("Remove %s level(s) of tree structure: %s", iterations, directory)
    dir_name = directory
    while iterations:
        sub_items = list(itertools.islice(dir_name.iterdir(), 2))
        if len(sub_items) != 1:
            raise IOError(f"Expected one item in directory: {dir_name}")
        dir_name = sub_items[0]
        if not dir_name.is_dir():
            raise IOError(f"Subitem is not a directory: {dir_name}, expected one subdirectory")
        iterations -= 1
    with TemporaryDirectory() as temp_dir:
        # first move to temp dir to avoid name collision
        shutil.move(str(dir_name.resolve()), temp_dir.path)
        # remove empty dirs
        for item in directory.iterdir():
            shutil.rmtree(item)
        # move subitems to target dir
        for item in temp_dir.path.joinpath(dir_name.name).iterdir():
            shutil.move(str(item), str(directory))


###############################
# function
###############################
def handle_remove_readonly(
    func: Callable[..., None], path: Union[str, Path], exc: Tuple[type, int, TracebackType]
) -> None:
    excvalue = exc[1]
    if func in (os.rmdir, os.remove) and excvalue == errno.EACCES:
        Path(path).chmod(stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)  # 0777
        func(path)
    else:
        raise PackagingError(excvalue)


def remove_tree(path: str) -> bool:
    if os.path.isdir(path) and os.path.exists(path):
        if is_windows():
            path = path.replace('/', '\\')
            # a funny thing is that rmdir does not set an exitcode it is just using the last set one
            try:
                cmd = ['rmdir', path, '/S', '/Q']
                run_command(command=cmd, cwd=str(Path.cwd()), only_error_case_output=True)
            except Exception:
                print_exc()
        else:
            # shutil.rmtree(path)
            run_command(["rm", "-rf", path], cwd=str(Path.cwd()), only_error_case_output=True)
    return not os.path.exists(path)


###############################
# function
###############################
# substitute all matches in files with replacement_string
def replace_in_files(filelist: List[str], regexp: str, replacement_string: str) -> None:
    regexp_obj = re.compile(regexp)
    for xfile in filelist:
        with open(xfile, 'r+', encoding="utf-8") as handle:
            old_contents = handle.read()
            new_contents = re.sub(regexp_obj, replacement_string, old_contents)
            if old_contents != new_contents:
                log.info("Replacement '%s' applied into: %s", replacement_string, xfile)
            handle.seek(0)
            handle.write(new_contents)
            handle.truncate()


###############################
# function
###############################
def safe_config_key_fetch(conf: ConfigParser, section: str, key: str) -> str:
    if not conf.has_section(section):
        return ''
    if not conf.has_option(section, key):
        return ''
    return str(config_section_map(conf, section)[key])


###############################
# function
###############################
def config_section_map(conf: ConfigParser, section: str) -> Dict[str, Any]:
    dict1: Dict[str, Any] = {}
    options = conf.options(section)
    for option in options:
        try:
            dict1[option] = conf.get(section, option)
            if dict1[option] == -1:
                log.info("skip: %s", option)
        except Exception as error:
            log.exception("exception on %s!", option, exc_info=error)
            dict1[option] = ''
    return dict1


def locate_executable(search_dir: Union[str, Path], patterns: List[str]) -> str:
    def _is_executable(path: Path) -> bool:
        return bool(path.stat().st_mode & stat.S_IEXEC)
    return locate_path(search_dir, patterns, filters=[os.path.isfile, _is_executable])


###############################
# Function
###############################
def locate_path(search_dir: Union[str, Path], patterns: List[str],
                filters: Optional[List[Callable[[Path], bool]]] = None) -> str:
    filters = filters or []
    matches = locate_paths(search_dir, patterns, filters)
    if len(matches) != 1:
        raise PackagingError(f"Expected one result in '{search_dir}' matching '{patterns}'"
                             f" and filters. Got '{matches}'")
    return matches.pop()


###############################
# Function
###############################
def locate_paths(search_dir: Union[str, Path], patterns: List[str],
                 filters: Optional[List[Callable[[Path], bool]]] = None) -> List[str]:
    filters = filters or []
    patterns = patterns if patterns else ["*"]
    paths = [p for p in Path(search_dir).rglob("*") if any(p.match(ptn) for ptn in patterns)]
    return [str(p) for p in paths if all(f(p) for f in filters)]


def calculate_relpath(target_path: Path, origin_path: Path) -> Path:
    """
    Figure out a path relative to origin, using pathlib

    Args:
        target_path: The target path to resolve
        origin_path: The origin path to resolve against

    Returns:
        A relative path based on the given two paths
    """
    try:
        return target_path.resolve().relative_to(origin_path.resolve())
    except ValueError:
        return Path("..") / calculate_relpath(target_path, origin_path.parent)


def calculate_runpath(file_full_path: Path, destination_lib_path: Path) -> str:
    """
    Calculate and return the relative RUNPATH for for the given file

    Args:
        file_full_path: A path to binary
        destination_lib_path: A path to destination lib

    Returns:
        RPath for destination lib path relative to $ORIGIN (binary file directory)

    Raises:
        FileNotFoundError: When the binary or destination path doesn't exist
    """
    bin_path = Path(file_full_path).resolve(strict=True)
    origin_path = bin_path.parent
    path_to_lib = destination_lib_path.resolve(strict=True)
    if path_to_lib == origin_path:
        full_rpath = Path("$ORIGIN")
    else:
        rpath: Path = calculate_relpath(path_to_lib, origin_path)
        full_rpath = Path("$ORIGIN") / rpath
    log.debug(" RPath target folder: %s", path_to_lib)
    log.debug(" Bin file:            %s", file_full_path)
    log.debug(" Calculated RPath:    %s", full_rpath)
    return str(full_rpath)


def read_file_rpath(file_path: Path) -> Optional[str]:
    """
    Read a RPath value from the given binary with the 'chrpath' tool.

    Args:
        file_path: A path to a binary file to read from

    Returns:
        The RPath from the binary if found, otherwise None
    """
    output = ""
    with suppress(CalledProcessError):
        output = run_cmd(cmd=["chrpath", "-l", str(file_path)])
    result = re.search(r":*.R.*PATH=.*", output)
    if result is None:
        return None
    rpath = result.group()
    index = rpath.index('=')
    rpath = rpath[index + 1:]
    return rpath


def update_file_rpath(file: Path, component_root: Path, destination_paths: str) -> None:
    """
    Change the RPATH/RUNPATH inside a binary file with the 'chrpath' tool.
    Removes any existing paths not relative to $ORIGIN (binary path)
    New RPATH/RUNPATH length must fit the space allocated inside the binary.

    Args:
        file: A path to a binary file that possibly contains a RPATH/RUNPATH
        component_root: A root path for the component
        destination_paths: A string containing the destination paths relative to root path

    Raises:
        PackagingError: When the RPATH/RUNPATH cannot be replaced (e.g. not enough space in binary)
    """
    # Read the existing rpath from the file. If not found, skip this file.
    existing_rpath = read_file_rpath(file)
    if existing_rpath is None:
        log.debug("No RPATH/RUNPATH found in %s", file)
        return
    # Create a list of new rpaths from 'destination_paths'
    rpaths = []
    for dest_path in destination_paths.split(':'):
        target_path = component_root / dest_path.lstrip("/")  # make relative to component root
        rpaths.append(calculate_runpath(file, target_path))
    # Look for $ORIGIN paths in existing rpath and add those to the new rpath
    origin_rpath = re.search(r"\$ORIGIN[^:\n]*", existing_rpath)
    if origin_rpath is not None:
        if origin_rpath.group() not in rpaths:
            rpaths.append(origin_rpath.group())
    # Join the final rpath tag value and update it inside the binary
    new_rpath = ':'.join(rpaths)
    try:
        log.debug("Change RPATH/RUNPATH [%s] -> [%s] for [%s]", existing_rpath, new_rpath, file)
        run_cmd(cmd=['chrpath', '-r', new_rpath, str(file)])
    except CalledProcessError as err:
        raise PackagingError(f"Unable to replace RPATH/RUNPATH in {file}") from err


def is_elf_binary(path: Path) -> bool:
    """
    Determines whether a path contains an ELF binary.

    Args:
        path: A file system path pointing to a possible executable

    Returns:
        True if the path is a regular ELF file with the executable bit set, otherwise False.
    """
    if path.is_file() and not path.is_symlink() and bool(path.stat().st_mode & stat.S_IEXEC):
        with path.open(mode="rb") as bin_file:
            if bin_file.read(4) == b"\x7fELF":
                return True
    return False


def handle_component_rpath(component_root_path: Path, destination_lib_paths: str) -> None:
    """
    Handle updating the RPath with 'destination_lib_paths' for all executable files in the given
    'component_root_path'.

    Args:
        component_root_path: Path to search executables from
        destination_lib_paths: String containing the paths to add to RPath

    Raises:
        PackagingError: When the 'chrpath' tool is not found in PATH
    """
    log.info("Handle RPATH/RUNPATH for all files")
    log.info("Component's root path: %s", component_root_path)
    log.info("Destination lib paths: %s", destination_lib_paths)
    if shutil.which("chrpath") is None:
        raise PackagingError("The 'chrpath' tool was not found in PATH")
    # loop on all binary files in component_root_path
    for file in locate_paths(component_root_path, ["*"], [is_elf_binary]):
        update_file_rpath(Path(file), component_root_path, destination_lib_paths)


###############################
# function
###############################
def clone_repository(
    repo_url: str,
    repo_branch_or_tag: str,
    destination_folder: str,
    full_clone: bool = False,
    init_subrepos: bool = False,
) -> None:
    log.info("--------------------------------------------------------------------")
    log.info("Cloning repository: %s", repo_url)
    log.info("Repo branch/tag: %s", repo_branch_or_tag)
    log.info("Destination: %s", destination_folder)
    log.info("--------------------------------------------------------------------")

    work_dir = os.path.dirname(os.path.realpath(__file__))
    if full_clone:
        cmd_args = ["git", "clone", repo_url, destination_folder, "-b", repo_branch_or_tag]
        run_cmd(cmd=cmd_args, cwd=work_dir)
    else:
        cmd_args = ["git", "init", destination_folder]
        run_cmd(cmd=cmd_args, cwd=work_dir)

        cmd_args = ["git", "fetch", repo_url, repo_branch_or_tag]
        run_cmd(cmd=cmd_args, cwd=destination_folder)

        cmd_args = ["git", "checkout", "FETCH_HEAD"]
        run_cmd(cmd=cmd_args, cwd=destination_folder)
    if init_subrepos:
        cmd_args = ["git", "submodule", "update", "--init"]
        run_cmd(cmd=cmd_args, cwd=destination_folder)


def get_tag_from_branch(directory: str) -> str:
    """
    Takes in a git directory path as a parameter.
    Return a tag if the current branch of the given directory is tagged but tag not checked out.
    Otherwise, return an empty string.
    """
    try:
        # Check if we already have checked out a tag
        run_cmd(cmd=["git", "symbolic-ref", "HEAD"], cwd=directory)
    except CalledProcessError:
        log.info("Already checked out a tag. THIS IS OKAY, PLEASE IGNORE THE ABOVE ERROR.")
        return ""
    try:
        # Check what sha1 we have checked out
        cmd_args = ["git", "rev-parse", "--short", "HEAD"]
        sha1 = run_cmd(cmd=cmd_args, cwd=directory).strip("\n")
        # Check if the sha1 matches to any tag
        cmd_args = ["git", "describe", "--exact-match", sha1]
        return run_cmd(cmd=cmd_args, cwd=directory).strip("\n")
    except CalledProcessError:
        log.info("No tag for branch. THIS IS OKAY, PLEASE IGNORE THE ABOVE ERROR.")
        return ""


###############################
# git archive given repository
###############################
def git_archive_repo(repo_and_ref: str) -> str:
    # define archive
    (repository, ref) = repo_and_ref.split("#")
    project_name = repository.split("/")[-1].split(".")[0]
    file_extension = ".tar.gz"
    if is_windows():
        file_extension = ".zip"
    work_dir = os.path.dirname(os.path.realpath(__file__))
    archive_name = os.path.join(work_dir, project_name + "-" + ref.replace("/", "-") + file_extension)
    if os.path.isfile(archive_name):
        os.remove(archive_name)
    # create temp directory
    with TemporaryDirectory() as checkout_dir:
        checkout_path = checkout_dir.path
        # clone given repo to temp
        clone_repository(repository, ref, str(checkout_path), full_clone=True, init_subrepos=True)
        # git archive repo with given name
        run_cmd(cmd=["git", "--no-pager", "archive", ref, "-o", archive_name], cwd=checkout_path)
        log.info("Created archive: %s", archive_name)
    return archive_name


###############################
# function
###############################
def extract_file(path: str, to_directory: str = ".") -> bool:
    cmd_args = []
    if path.endswith('.tar'):
        cmd_args = ['tar', '-xf', path]
    elif path.endswith('.tar.gz') or path.endswith('.tgz'):
        cmd_args = ['tar', '-xzf', path]
    elif path.endswith('.tar.xz'):
        cmd_args = ['tar', '-xf', path]
    elif path.endswith('.tar.bz2') or path.endswith('.tbz'):
        cmd_args = ['tar', '-xjf', path]
    elif path.endswith(('.7z', '.zip', '.gz', '.xz', '.bz2', '.qbsp')):
        cmd_args = ['7z', 'x', path]
    else:
        log.warning("Extract fail: %s. Not an archive or appropriate extractor was not found", path)
        return False

    ret = run_command(cmd_args, cwd=to_directory, only_error_case_output=True)
    if ret:
        raise RuntimeError(f"Failure running the last command: {ret}")
    return True


###############################
# function
###############################
def list_as_string(argument_list: List[Any]) -> str:
    output = ' '.join([str(i) for i in argument_list])
    return output


###############################
# function
###############################
def remote_path_exists(remote_addr: str, path_to_check: str, ssh_command: str = 'ssh') -> bool:
    text_to_print = 'REMOTE_PATH_EXISTS'
    cmd_args = [ssh_command, remote_addr, "bash", "-c"]
    cmd_args += ['"if [ -e ' + path_to_check + " ] ; then echo " + text_to_print + ' ; fi"']
    check = run_cmd(cmd=cmd_args).rstrip()
    return bool(check == text_to_print)


###############################
# function
###############################
def create_mac_disk_image(execution_path: str, file_directory: str, file_base_name: str, image_size: str = '4g') -> None:
    # create disk image
    src_folder = os.path.join(file_directory, file_base_name + '.app')
    dmg_path = os.path.join(file_directory, file_base_name + '.dmg')
    cmd_args = ['hdiutil', 'create', '-srcfolder', src_folder, '-volname', file_base_name]
    cmd_args += ['-format', 'UDBZ', dmg_path, '-ov', '-scrub', '-size', image_size]
    run_cmd(cmd=cmd_args, cwd=execution_path)


###############################
# function
###############################
def create_extract_function(file_path: str, target_path: str) -> Callable[[], Any]:
    Path(target_path).mkdir(parents=True, exist_ok=True)
    working_dir = os.path.dirname(file_path)
    if file_path.endswith('.tar.gz'):
        return lambda: run_command(['tar', 'zxf', file_path, '-C', target_path], working_dir)
    return lambda: run_command(['7z', 'x', '-y', file_path, '-o' + target_path], working_dir)


###############################
# function
###############################
def create_download_and_extract_tasks(url: str, target_path: str, temp_path: str) -> Tuple[Task, Task]:
    filename = Path(urlparse(url).path).name
    sevenzip_file = os.path.join(temp_path, filename)
    download_task = Task(f"download '{url}' to '{sevenzip_file}'", function=None)
    download_task.add_function(download, url, sevenzip_file)
    extract_task = Task(f"extract '{sevenzip_file}' to '{target_path}'", function=None)
    extract_task.add_function(create_extract_function(sevenzip_file, target_path))
    return (download_task, extract_task)


###############################
# function
###############################
def create_download_extract_task(url: str, target_path: str, temp_path: str) -> Task:
    filename = Path(urlparse(url).path).name
    sevenzip_file = os.path.join(temp_path, filename)
    download_extract_task = Task(f"download {url} to {sevenzip_file} and extract it to {target_path}", function=None)
    download_extract_task.add_function(download, url, sevenzip_file)
    download_extract_task.add_function(create_extract_function(sevenzip_file, target_path))
    return download_extract_task


###############################
# function
###############################
def create_qt_download_task(module_urls: List[str], target_qt5_path: str, temp_path: str, caller_arguments: Optional[Namespace]) -> Task:
    qt_task = Task(f'download and extract Qt to "{target_qt5_path}"', function=None)
    download_work = ThreadedWork(f'download Qt packages to "{temp_path}"')
    unzip_task = Task(f'extracting packages to "{target_qt5_path}"', function=None)
    # add Qt modules
    for module_url in module_urls:
        if uri_exists(module_url):
            (download_task, extract_task) = create_download_and_extract_tasks(
                module_url, target_qt5_path, temp_path
            )
            download_work.add_task_object(download_task)
            unzip_task.add_function(extract_task.do_task)
        else:
            log.warning("could not find '%s' for download", module_url)
    # add icu, d3dcompiler, opengl32, openssl
    target_path = os.path.join(target_qt5_path, 'bin' if is_windows() else 'lib')
    if caller_arguments:
        if not is_macos() and hasattr(caller_arguments, 'icu7z') and caller_arguments.icu7z:
            (download_task, extract_task) = create_download_and_extract_tasks(
                caller_arguments.icu7z, target_path, temp_path
            )
            download_work.add_task_object(download_task)
            unzip_task.add_function(extract_task.do_task)
        if is_windows():
            if hasattr(caller_arguments, 'd3dcompiler7z') and caller_arguments.d3dcompiler7z:
                (download_task, extract_task) = create_download_and_extract_tasks(
                    caller_arguments.d3dcompiler7z, target_path, temp_path
                )
                download_work.add_task_object(download_task)
                unzip_task.add_function(extract_task.do_task)
            if hasattr(caller_arguments, 'opengl32sw7z') and caller_arguments.opengl32sw7z:
                (download_task, extract_task) = create_download_and_extract_tasks(
                    caller_arguments.opengl32sw7z, target_path, temp_path
                )
                download_work.add_task_object(download_task)
                unzip_task.add_function(extract_task.do_task)
            if hasattr(caller_arguments, 'openssl7z') and caller_arguments.openssl7z:
                (download_task, extract_task) = create_download_and_extract_tasks(
                    caller_arguments.openssl7z, target_path, temp_path
                )
                download_work.add_task_object(download_task)
                unzip_task.add_function(extract_task.do_task)
    qt_task.add_function(download_work.run)
    qt_task.add_function(unzip_task.do_task)
    return qt_task


def patch_qt(qt5_path: str) -> None:
    log.info("##### patch Qt #####")
    qmake_binary = os.path.join(qt5_path, 'bin', 'qmake')
    # write qt.conf
    with open(os.path.join(qt5_path, 'bin', 'qt.conf'), "w", encoding="utf-8") as qt_conf_file:
        qt_conf_file.write("[Paths]" + os.linesep)
        qt_conf_file.write("Prefix=.." + os.linesep)
    # fix rpaths
    if is_linux():
        handle_component_rpath(Path(qt5_path), 'lib')
    log.info("##### patch Qt ##### ... done")
    run_command(qmake_binary + " -query", qt5_path)
