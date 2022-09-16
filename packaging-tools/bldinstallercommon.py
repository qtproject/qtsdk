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

import errno
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

# need to include this for win platforms as long path names cause problems
if is_windows():
    import win32api  # type: ignore # pylint: disable=E0401

log = init_logger(__name__, debug_mode=False)

MAX_DEBUG_PRINT_LENGTH = 10000


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
    # windows has length limit for path names so try to truncate them as much as possible
    if is_windows():
        srcdir = win32api.GetShortPathName(srcdir)
        dstdir = win32api.GetShortPathName(dstdir)
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
            os.mkdir(dstfname)
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
    # windows has length limit for path names so try to truncate them as much as possible
    if is_windows():
        source_dir = win32api.GetShortPathName(source_dir)
        dest_dir = win32api.GetShortPathName(dest_dir)
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


def remove_one_tree_level(directory: str) -> None:
    dircontents = os.listdir(directory)
    items = len(dircontents)
    if items == 1:
        dir_name = dircontents[0]
        full_dir_name = os.path.join(directory, dir_name)
        # avoid directory name collision by first moving to temporary dir
        with TemporaryDirectory() as tempdir_base:
            tempdir = tempdir_base.path / 'a'  # dummy name
            shutil.move(full_dir_name, str(tempdir))
            move_tree(str(tempdir), directory)
    else:
        raise IOError(f'Cannot remove one level of directory structure of "{dir}", it has {items} subdirectories')


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
            path = win32api.GetShortPathName(path.replace('/', '\\'))
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


###############################
# Function
###############################
def requires_rpath(file_path: str) -> bool:
    if is_linux():
        if not os.access(file_path, os.X_OK):
            return False
        with suppress(CalledProcessError):
            output = run_cmd(cmd=["chrpath", "-l", file_path])
            if output:
                return re.search(r":*.R.*PATH=", output) is not None
    return False


###############################
# Function
###############################
def sanity_check_rpath_max_length(file_path: str, new_rpath: str) -> bool:
    if is_linux():
        if not os.access(file_path, os.X_OK):
            return False
        result = None
        with suppress(CalledProcessError):
            output = run_cmd(cmd=["chrpath", "-l", file_path])
            result = re.search(r":*.R.*PATH=.*", output)
        if result is None:
            log.info("No RPath found from given file: %s", file_path)
        else:
            rpath = result.group()
            index = rpath.index('=')
            rpath = rpath[index + 1:]
            space_for_new_rpath = len(rpath)
            if len(new_rpath) > space_for_new_rpath:
                log.warning("Warning - Not able to process RPath for file: %s", file_path)
                log.warning("New RPath [%s] length: %s", new_rpath, str(len(new_rpath)))
                log.warning("Space available inside the binary: %s", str(space_for_new_rpath))
                raise IOError()
    return True


###############################
# Function
###############################
def pathsplit(path: str, rest: Optional[List[str]] = None) -> List[str]:
    rest = rest or []
    (head, tail) = os.path.split(path)
    if len(head) < 1:
        return [tail] + rest
    if len(tail) < 1:
        return [head] + rest
    return pathsplit(head, [tail] + rest)


def commonpath(list1: List[str], list2: List[str], common: Optional[List[str]] = None) -> Tuple[List[str], List[str], List[str]]:
    common = common or []
    if len(list1) < 1:
        return (common, list1, list2)
    if len(list2) < 1:
        return (common, list1, list2)
    if list1[0] != list2[0]:
        return (common, list1, list2)
    return commonpath(list1[1:], list2[1:], common + [list1[0]])


def calculate_relpath(path1: str, path2: str) -> str:
    (_, list1, list2) = commonpath(pathsplit(path1), pathsplit(path2))
    path = []
    if len(list1) > 0:
        tmp = '..' + os.sep
        path = [tmp * len(list1)]
    path = path + list2
    return os.path.join(*path)


##############################################################
# Calculate the relative RPath for the given file
##############################################################
def calculate_rpath(file_full_path: str, destination_lib_path: str) -> str:
    if not os.path.isfile(file_full_path):
        raise IOError(f"*** Not a valid file: {file_full_path}")

    bin_path = os.path.dirname(file_full_path)
    path_to_lib = os.path.abspath(destination_lib_path)
    full_rpath = ''
    if path_to_lib == bin_path:
        full_rpath = '$ORIGIN'
    else:
        rpath = calculate_relpath(bin_path, path_to_lib)
        full_rpath = '$ORIGIN' + os.sep + rpath

    log.debug("----------------------------------------")
    log.debug(" RPath target folder: %s", path_to_lib)
    log.debug(" Bin file:            %s", file_full_path)
    log.debug(" Calculated RPath:    %s", full_rpath)

    return full_rpath


##############################################################
# Handle the RPath in the given component files
##############################################################
def handle_component_rpath(component_root_path: str, destination_lib_paths: str) -> None:
    log.info("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
    log.info("Handle RPath")
    log.info("")
    log.info("Component root path:  %s", component_root_path)
    log.info("Destination lib path: %s", destination_lib_paths)

    # loop on all files
    for root, _, files in os.walk(component_root_path):
        for name in files:
            file_full_path = os.path.join(root, name)
            if not os.path.isdir(file_full_path) and not os.path.islink(file_full_path):
                if requires_rpath(file_full_path):
                    rpaths = []
                    for destination_lib_path in destination_lib_paths.split(':'):
                        dst = os.path.normpath(component_root_path + os.sep + destination_lib_path)
                        rpath = calculate_rpath(file_full_path, dst)
                        rpaths.append(rpath)

                    # look for existing $ORIGIN path in the binary
                    origin_rpath = None
                    with suppress(CalledProcessError):
                        output = run_cmd(cmd=["chrpath", "-l", file_full_path])
                        origin_rpath = re.search(r"\$ORIGIN[^:\n]*", output)

                    if origin_rpath is not None:
                        if origin_rpath.group() not in rpaths:
                            rpaths.append(origin_rpath.group())

                    rpath = ':'.join(rpaths)
                    if sanity_check_rpath_max_length(file_full_path, rpath):
                        log.debug("RPath value: [%s] for file: [%s]", rpath, file_full_path)
                        cmd_args = ['chrpath', '-r', rpath, file_full_path]
                        # force silent operation
                        work_dir = os.path.dirname(os.path.realpath(__file__))
                        run_cmd(cmd=cmd_args, cwd=work_dir)


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
    elif path.endswith(('.7z', '.zip', '.gz', '.xz', '.bz2')):
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
    filename = os.path.basename(urlparse(url).path)
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
    filename = os.path.basename(urlparse(url).path)
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
        handle_component_rpath(qt5_path, 'lib')
    log.info("##### patch Qt ##### ... done")
    run_command(qmake_binary + " -query", qt5_path)
