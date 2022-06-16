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

import errno
import fnmatch
import os
import re
import shutil
import subprocess
from subprocess import STDOUT
import tempfile
import sys
import stat
import traceback
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

from bld_utils import runCommand, download, is_windows, is_macos, is_linux
from threadedwork import Task, ThreadedWork
from typing import Callable, Union, List
from installer_utils import PackagingError
from runner import do_execute_sub_process


# need to include this for win platforms as long path names
# cause problems
if is_windows():
    import win32api

DEBUG_RPATH             = False
MAX_DEBUG_PRINT_LENGTH  = 10000


###############################
# function
###############################
def is_content_url_valid(url):
    # check first if the url points to file on local file system
    if os.path.isfile(url):
        return True
    # throws error if url does not point to valid object
    try:
        response = urllib.request.urlopen(url)
        total_size = response.info().get('Content-Length').strip()
        return int(total_size) > 0
    except Exception:
        pass
    return False


###############################
# function
###############################
CURRENT_DOWNLOAD_PERCENT = 0
def dlProgress(count, blockSize, totalSize):
    global CURRENT_DOWNLOAD_PERCENT
    percent = int(count*blockSize*100/totalSize)
    # produce only reasonable amount of prints into stdout
    if percent > CURRENT_DOWNLOAD_PERCENT:
        CURRENT_DOWNLOAD_PERCENT = percent
        sys.stdout.write("\r" + "     Downloading: %d%%" % percent)
        sys.stdout.flush()
    if count*blockSize >= totalSize:
        CURRENT_DOWNLOAD_PERCENT = 0
        print('\n')


###############################
# function
###############################
def retrieve_url(url, savefile):
    try:
        savefile_tmp = savefile + '.tmp'
        urllib.request.urlcleanup()
        urllib.request.urlretrieve(url, savefile_tmp, reporthook=dlProgress)
        shutil.move(savefile_tmp, savefile)
    except Exception:
        exc = sys.exc_info()[0]
        print(exc)
        try:
            os.remove(savefile_tmp)
        except Exception:  # swallow, do not shadow actual error
            pass
        raise exc


###############################
# function
###############################
def search_for_files(
    search_path: Union[str, Path], suffixes: List[str], rgx_pattern: str
) -> List[str]:
    pattern = re.compile(rgx_pattern, flags=re.MULTILINE)

    def _matches_rgx(path: Path):
        if rgx_pattern:
            with open(path, 'r') as f:
                return bool(pattern.search(f.read()))
        return True
    return locate_paths(search_path, suffixes, filters=[os.path.isfile, _matches_rgx])


###############################
# function
###############################
def move_tree(srcdir, dstdir, pattern=None):
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
        elif pattern is None or fnmatch.fnmatch(name, pattern):
            if os.path.islink(srcfname):  # shutil.move fails moving directory symlinks over file system bounds...
                linkto = os.readlink(srcfname)
                os.symlink(linkto, dstfname)
                os.remove(srcfname)
            else:
                shutil.move(srcfname, dstfname)


###############################
# function
###############################
def copy_tree(source_dir, dest_dir):
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
                raise IOError('given full_file_name length [%s] too long for Windows: %s' % (len(full_file_name), full_file_name))
        if os.path.isdir(full_file_name):
            Path(dest_dir + os.sep + file_name).mkdir(parents=True, exist_ok=True)
            copy_tree(full_file_name, dest_dir + os.sep + file_name)
        if os.path.isfile(full_file_name):
            shutil.copy(full_file_name, dest_dir)

def remove_one_tree_level(directory):
    dircontents = os.listdir(directory)
    items = len(dircontents)
    if items == 1:
        dir_name = dircontents[0]
        full_dir_name = os.path.join(directory, dir_name)
        # avoid directory name collision by first moving to temporary dir
        tempdir_base = tempfile.mkdtemp()
        tempdir = os.path.join(tempdir_base, 'a')  # dummy name
        shutil.move(full_dir_name, tempdir)
        move_tree(tempdir, directory)
        remove_tree(tempdir_base)
    else:
        raise IOError('Cannot remove one level of directory structure of "%s", it has %s subdirectories' % (dir, items))

###############################
# function
###############################
def handle_remove_readonly(func, path, exc):
    excvalue = exc[1]
    if func in (os.rmdir, os.remove) and excvalue.errno == errno.EACCES:
        os.chmod(path, stat.S_IRWXU| stat.S_IRWXG| stat.S_IRWXO)  # 0777
        func(path)
    else:
        raise

def remove_tree(path):
    if os.path.isdir(path) and os.path.exists(path):
        if is_windows():
            path = win32api.GetShortPathName(path.replace('/', '\\'))
            # a funny thing is that rmdir does not set an exitcode it is just using the last set one
            try:
                runCommand(['rmdir', path, '/S', '/Q'], os.getcwd(), onlyErrorCaseOutput=True)
            except Exception:
                traceback.print_exc()
                pass
        else:
            # shutil.rmtree(path)
            runCommand(['rm', '-rf', path], os.getcwd(), onlyErrorCaseOutput=True)
    return not os.path.exists(path)


###############################
# function
###############################
# substitute all matches in files with replacement_string
def replace_in_files(filelist, regexp, replacement_string):
    regexp_obj = re.compile(regexp)
    for xfile in filelist:
        with open(xfile, 'r+', encoding="utf-8") as f:
            old_contents = f.read()
            new_contents = re.sub(regexp_obj, replacement_string, old_contents)
            if old_contents != new_contents:
                print(f"Replacement '{replacement_string}' applied into: {xfile}")
            f.seek(0)
            f.write(new_contents)
            f.truncate()


###############################
# function
###############################
def ensure_text_file_endings(filename):
    print('------------ ensure_text_file_endings ----------------')
    if os.path.isdir(filename):
        print('*** Warning, given file is directory? Did nothing for: ' + filename)
        return
    data = open(filename, "rb").read()
    if b'\0' in data:
        print('*** Warning, given file is binary? Did nothing for: ' + filename)
        return
    if is_windows():
        newdata = re.sub(b"\r?\n", b"\r\n", data)
        if newdata != data:
            print('File endings changed for: ' + filename)
            f = open(filename, "wb")
            f.write(newdata)
            f.close()
    print('--------------------------------------------------------------------')


###############################
# function
###############################
def safe_config_key_fetch(conf, section, key):
    if not conf.has_section(section):
        return ''
    if not conf.has_option(section, key):
        return ''
    return config_section_map(conf, section)[key]


###############################
# function
###############################
def config_section_map(conf, section):
    dict1 = {}
    options = conf.options(section)
    for option in options:
        try:
            dict1[option] = conf.get(section, option)
            if dict1[option] == -1:
                print('skip: %s' % option)
        except Exception:
            print('exception on %s!' % option)
            dict1[option] = ''
    return dict1


def locate_executable(search_dir: Union[str, Path], patterns: List[str]) -> str:
    def _is_executable(path: Path):
        return bool(path.stat().st_mode & stat.S_IEXEC)
    return locate_path(search_dir, patterns, filters=[os.path.isfile, _is_executable])


###############################
# Function
###############################
def locate_path(search_dir: Union[str, Path], patterns: List[str],
                filters: List[Callable[[Path], bool]] = []) -> str:
    matches = locate_paths(search_dir, patterns, filters)
    if len(matches) != 1:
        raise PackagingError(f"Expected one result in '{search_dir}' matching '{patterns}'"
                             f" and filters. Got '{matches}'")
    return matches.pop()


###############################
# Function
###############################
def locate_paths(search_dir: Union[str, Path], patterns: List[str],
                 filters: List[Callable[[Path], bool]] = []) -> List[str]:
    patterns = patterns if patterns else ["*"]
    paths = [p for p in Path(search_dir).rglob("*") if any(p.match(ptn) for ptn in patterns)]
    return [str(p) for p in paths if all(f(p) for f in filters)]

###############################
# Function
###############################
# original snippet: http://code.activestate.com/recipes/173220-test-if-a-file-or-string-is-text-or-binary/

text_characters = "".join(list(map(chr, list(range(32, 127)))) + list("\n\r\t\b"))
trans_table      = str.maketrans("", "", text_characters)

def is_text(s):
    try:
        if "\0" in s:
            return 0
    except TypeError:
        if b"\0" in s:
            return 0
    if not s:  # Empty files are considered text
        return 1
    # Get the non-text characters (maps a character to itself then
    # use the 'remove' option to get rid of the text characters.)
    t = s.translate(trans_table)
    # If more than 30% non-text characters, then
    # this is considered a binary file
    if len(t)/len(s) > 0.30:
        return 0
    return 1

def is_text_file(filename, blocksize = 512):
    try:
        return is_text(open(filename).read(blocksize))
    except UnicodeDecodeError:
        return is_text(open(filename, 'rb').read(blocksize))


###############################
# Function
###############################
def requires_rpath(file_path):
    if is_linux():
        if not os.access(file_path, os.X_OK):
            return False
        return (re.search(r':*.R.*PATH=',
            subprocess.Popen(['chrpath', '-l', file_path],
                stdout=subprocess.PIPE).stdout.read().decode()) is not None)
    return False


###############################
# Function
###############################
def sanity_check_rpath_max_length(file_path, new_rpath):
    if is_linux():
        if not os.access(file_path, os.X_OK):
            return False
        result = re.search(r':*.R.*PATH=.*', subprocess.Popen(['chrpath', '-l', file_path], stdout=subprocess.PIPE).stdout.read().decode())
        if not result:
            print('*** No RPath found from given file: ' + file_path)
        else:
            rpath = result.group()
            index = rpath.index('=')
            rpath = rpath[index+1:]
            space_for_new_rpath = len(rpath)
            if len(new_rpath) > space_for_new_rpath:
                print('*** Warning - Not able to process RPath for file: ' + file_path)
                print('*** Required length for new RPath [' + new_rpath + '] is: ' + str(len(new_rpath)))
                print('*** Space available for new RPath inside the binary is: ' + str(space_for_new_rpath))
                raise IOError()
    return True


###############################
# Function
###############################
def pathsplit(p, rest=[]):
    (h, t) = os.path.split(p)
    if len(h) < 1:
        return [t]+rest
    if len(t) < 1:
        return [h]+rest
    return pathsplit(h, [t]+rest)

def commonpath(l1, l2, common=[]):
    if len(l1) < 1:
        return (common, l1, l2)
    if len(l2) < 1:
        return (common, l1, l2)
    if l1[0] != l2[0]:
        return (common, l1, l2)
    return commonpath(l1[1:], l2[1:], common+[l1[0]])

def calculate_relpath(p1, p2):
    (common, l1, l2) = commonpath(pathsplit(p1), pathsplit(p2))
    p = []
    if len(l1) > 0:
        tmp = '..' + os.sep
        p = [ tmp * len(l1) ]
    p = p + l2
    return os.path.join( *p )


##############################################################
# Calculate the relative RPath for the given file
##############################################################
def calculate_rpath(file_full_path, destination_lib_path):
    if not os.path.isfile(file_full_path):
        raise IOError('*** Not a valid file: %s' % file_full_path)

    bin_path    = os.path.dirname(file_full_path)
    path_to_lib = os.path.abspath(destination_lib_path)
    full_rpath = ''
    if path_to_lib == bin_path:
        full_rpath = '$ORIGIN'
    else:
        rp = calculate_relpath(bin_path, path_to_lib)
        full_rpath = '$ORIGIN' + os.sep + rp

    if DEBUG_RPATH:
        print('        ----------------------------------------')
        print('         RPath target folder: ' + path_to_lib)
        print('         Bin file:            ' + file_full_path)
        print('         Calculated RPath:    ' + full_rpath)

    return full_rpath


##############################################################
# Handle the RPath in the given component files
##############################################################
def handle_component_rpath(component_root_path, destination_lib_paths):
    print('        @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@')
    print('        Handle RPath')
    print('')
    print('        Component root path:  ' + component_root_path)
    print('        Destination lib path: ' + destination_lib_paths)

    # loop on all files
    for root, dirs, files in os.walk(component_root_path):
        for name in files:
            file_full_path = os.path.join(root, name)
            if not os.path.isdir(file_full_path) and not os.path.islink(file_full_path):
                if requires_rpath(file_full_path):
                    rpaths = []
                    for destination_lib_path in destination_lib_paths.split(':'):
                        dst = os.path.normpath(component_root_path + os.sep + destination_lib_path)
                        rp = calculate_rpath(file_full_path, dst)
                        rpaths.append(rp)

                    # look for existing $ORIGIN path in the binary
                    origin_rpath = re.search(r'\$ORIGIN[^:\n]*',
                        subprocess.Popen(['chrpath', '-l', file_full_path],
                        stdout=subprocess.PIPE).stdout.read().decode())

                    if origin_rpath and origin_rpath.group() not in rpaths:
                        rpaths.append(origin_rpath.group())

                    rp = ':'.join(rpaths)
                    if sanity_check_rpath_max_length(file_full_path, rp):
                        # print '        RPath value: [' + rp + '] for file: [' + file_full_path + ']'
                        cmd_args = ['chrpath', '-r', rp, file_full_path]
                        # force silent operation
                        work_dir = os.path.dirname(os.path.realpath(__file__))
                        do_execute_sub_process(cmd_args, work_dir)


###############################
# function
###############################
def clone_repository(repo_url, repo_branch_or_tag, destination_folder, full_clone = False, init_subrepos = False):
    print('--------------------------------------------------------------------')
    print('Cloning repository: ' + repo_url)
    print('        branch/tag: ' + repo_branch_or_tag)
    print('Dest:               ' + destination_folder)
    print('--------------------------------------------------------------------')

    work_dir = os.path.dirname(os.path.realpath(__file__))
    if full_clone:
        cmd_args = ['git', 'clone', repo_url, destination_folder, '-b', repo_branch_or_tag]
        do_execute_sub_process(cmd_args, work_dir)
    else:
        cmd_args = ['git', 'init', destination_folder]
        do_execute_sub_process(cmd_args, work_dir)

        cmd_args = ['git', 'fetch', repo_url, repo_branch_or_tag]
        do_execute_sub_process(cmd_args, destination_folder)

        cmd_args = ['git', 'checkout', 'FETCH_HEAD']
        do_execute_sub_process(cmd_args, destination_folder)
    if init_subrepos:
        cmd_args = ['git', 'submodule', 'update', '--init']
        do_execute_sub_process(cmd_args, destination_folder)

#####################################################################
# This function returns a tag if the given branch is tagged. Branch
# parameter can be also a tag, in that case we return empty string.
#####################################################################
def get_tag_from_branch(directory, branch):
    tag = ""
    # Check if we already have checked out a tag
    cmd_args = ['git', 'symbolic-ref', 'HEAD']
    return_code, tag = do_execute_sub_process(cmd_args, directory, False, True)
    if return_code != -1:
        print("Already checked out a tag. THIS IS TOTALLY OK, PLEASE IGNORE THE ABOVE ERROR.")
        tag = ""
    else:
        # Check what sha1 we have checked out
        cmd_args = ['git', 'rev-parse', '--short', 'HEAD']
        return_code, sha1 = do_execute_sub_process(cmd_args, directory, False, True)
        if return_code == -1:
            # Check if the sha1 matches to any tag
            sha1 = sha1.strip('\n')
            cmd_args = ['git', 'describe', '--exact-match', sha1]
            return_code, tag = do_execute_sub_process(cmd_args, directory, False, True)
            tag = tag.strip('\n')
            if return_code != -1:
                print('No tag found for branch. THIS IS TOTALLY OK, PLEASE IGNORE THE ABOVE ERROR.')
                tag = ""
    return tag


###############################
# git archive given repository
###############################
def git_archive_repo(repo_and_ref):
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
    checkout_dir = tempfile.mkdtemp()
    # clone given repo to temp
    clone_repository(repository, ref, checkout_dir, full_clone=True, init_subrepos=True)
    # git archive repo with given name
    archive_file = open(archive_name, 'w')
    subprocess.check_call("git --no-pager archive %s" % (ref), stdout=archive_file, stderr=STDOUT, shell=True, cwd=checkout_dir)
    archive_file.close()
    print('Created archive: {0}'.format(archive_name))
    shutil.rmtree(checkout_dir, ignore_errors=True)
    return archive_name


###############################
# function
###############################
def extract_file(path, to_directory='.'):
    cmd_args = []
    if path.endswith('.tar'):
        cmd_args = ['tar', '-xf', path]
    elif path.endswith('.tar.gz') or path.endswith('.tgz'):
        cmd_args = ['tar', '-xzf', path]
    elif path.endswith('.tar.xz'):
        cmd_args = ['tar', '-xf', path]
    elif path.endswith('.tar.bz2') or path.endswith('.tbz'):
        cmd_args = ['tar', '-xjf', path]
    elif path.endswith('.7z') or path.endswith('.zip'):
        cmd_args = ['7z', 'x', path]
    else:
        print('Did not extract the file! Not archived or no appropriate extractor was found: ' + path)
        return False

    ret = runCommand(cmd_args, currentWorkingDirectory=to_directory, onlyErrorCaseOutput=True)
    if ret:
        raise RuntimeError('Failure running the last command: %i' % ret)
    return True


###############################
# function
###############################
def list_as_string(argument_list):
    output = ' '.join([str(i) for i in argument_list])
    return output


###############################
# function
###############################
def remote_path_exists(remote_addr, path_to_check, ssh_command = 'ssh'):
    text_to_print = 'REMOTE_PATH_EXISTS'
    cmd_args = [ssh_command, remote_addr, 'bash', '-c', '\"if [ -e ' + path_to_check + ' ] ; then echo ' + text_to_print + ' ; fi\"']
    output = do_execute_sub_process(cmd_args, os.getcwd(), get_output=True)
    check = output[1].rstrip()
    return check == text_to_print


###############################
# function
###############################
def create_mac_disk_image(execution_path, file_directory, file_base_name, image_size = '4g'):
    # create disk image
    cmd_args = ['hdiutil', 'create', '-srcfolder',
                os.path.join(file_directory, file_base_name + '.app'),
                '-volname', file_base_name,
                '-format', 'UDBZ',
                os.path.join(file_directory, file_base_name + '.dmg'),
                '-ov', '-scrub', '-size', image_size]
    do_execute_sub_process(cmd_args, execution_path)


###############################
# function
###############################
def rename_android_soname_files(qt5_base_path):
    print ('---------- Renaming .so name files in ' + qt5_base_path + ' ----------------')
    # QTBUG-33793
    # temporary solution for Android on Windows compilations
    # rename the .so files for Android on Windows
    # find the lib directory under the install directory for essentials
    try:
        print ('Trying to locate /lib from: ' + qt5_base_path)
        lib_dir = locate_path(qt5_base_path, ["lib"], filters=[os.path.isdir])
        print ('Match found: ' + lib_dir)
        # regex for Qt version, eg. 5.2.0
        # assuming that Qt version will always have one digit, eg, 5.2.0
        p = re.compile(r'\d\.\d\.\d')
        # just list the files with a pattern like 'libQt5Core.so.5.2.0'
        files = [f for f in os.listdir(lib_dir) if re.match(r'lib.*\.so\..*', f)]
        for name in files:
            # if name is something like 'libQt5Core.so.5.2.0' then
            # filename, so, version = ['libQt5Core', 'so', '5.2.0']
            filename, so, version = name.split(os.extsep, 2)
            # let's just rename the appropriate files
            if filename.startswith('lib') and so == 'so' and p.match(version) is not None:
                old_filepath = os.path.join(lib_dir, name)
                new_filepath = os.path.join(lib_dir, filename + '.so')
                shutil.move(old_filepath, new_filepath)
                print ('---> Old file name : ' + old_filepath)
                print ('---> New file name : ' + new_filepath)
            else:
                print ('*** Warning! The file : ' + filename + ' does not match the pattern')
    except PackagingError:
        print('*** No .so files found to be renamed as /lib was not found. Skipping.')


###############################
# function
###############################
def create_extract_function(file_path, target_path, caller_arguments = None):
    Path(target_path).mkdir(parents=True, exist_ok=True)
    working_dir = os.path.dirname(file_path)
    if file_path.endswith('.tar.gz'):
        return lambda: runCommand(['tar', 'zxf', file_path, '-C', target_path], working_dir, caller_arguments)
    return lambda: runCommand(['7z', 'x', '-y', file_path, '-o'+target_path], working_dir, caller_arguments)

###############################
# function
###############################
def create_download_and_extract_tasks(url, target_path, temp_path, caller_arguments):
    filename = os.path.basename(urllib.parse.urlparse(url).path)
    sevenzip_file = os.path.join(temp_path, filename)
    download_task = Task('download "{0}" to "{1}"'.format(url, sevenzip_file))
    download_task.addFunction(download, url, sevenzip_file)
    extract_task = Task('extract "{0}" to "{1}"'.format(sevenzip_file, target_path))
    extract_task.addFunction(create_extract_function(sevenzip_file, target_path, caller_arguments))
    return (download_task, extract_task)


###############################
# function
###############################
def create_download_extract_task(url, target_path, temp_path, caller_arguments):
    filename = os.path.basename(urllib.parse.urlparse(url).path)
    sevenzip_file = os.path.join(temp_path, filename)
    download_extract_task = Task("download {0} to {1} and extract it to {2}".format(url, sevenzip_file, target_path))
    download_extract_task.addFunction(download, url, sevenzip_file)
    download_extract_task.addFunction(create_extract_function(sevenzip_file, target_path, caller_arguments))
    return download_extract_task

###############################
# function
###############################
def create_qt_download_task(module_urls, target_qt5_path, temp_path, caller_arguments):
    qt_task = Task('download and extract Qt to "{0}"'.format(target_qt5_path))
    download_work = ThreadedWork('download Qt packages to "{0}"'.format(temp_path))
    unzip_task = Task('extracting packages to "{0}"'.format(target_qt5_path))
    # add Qt modules
    for module_url in module_urls:
        if is_content_url_valid(module_url):
            (download_task, extract_task) = create_download_and_extract_tasks(module_url,
                                                target_qt5_path, temp_path, caller_arguments)
            download_work.addTaskObject(download_task)
            unzip_task.addFunction(extract_task.do)
        else:
            print('warning: could not find "{0}" for download'.format(module_url))
    # add icu, d3dcompiler, opengl32, openssl
    target_path = os.path.join(target_qt5_path, 'bin' if is_windows() else 'lib')
    if not is_macos() and hasattr(caller_arguments, 'icu7z') and caller_arguments.icu7z:
        (download_task, extract_task) = create_download_and_extract_tasks(caller_arguments.icu7z,
                                                target_path, temp_path, caller_arguments)
        download_work.addTaskObject(download_task)
        unzip_task.addFunction(extract_task.do)
    if is_windows():
        if hasattr(caller_arguments, 'd3dcompiler7z') and caller_arguments.d3dcompiler7z:
            (download_task, extract_task) = create_download_and_extract_tasks(caller_arguments.d3dcompiler7z,
                                                    target_path, temp_path, caller_arguments)
            download_work.addTaskObject(download_task)
            unzip_task.addFunction(extract_task.do)
        if hasattr(caller_arguments, 'opengl32sw7z') and caller_arguments.opengl32sw7z:
            (download_task, extract_task) = create_download_and_extract_tasks(caller_arguments.opengl32sw7z,
                                                    target_path, temp_path, caller_arguments)
            download_work.addTaskObject(download_task)
            unzip_task.addFunction(extract_task.do)
        if hasattr(caller_arguments, 'openssl7z') and caller_arguments.openssl7z:
            (download_task, extract_task) = create_download_and_extract_tasks(caller_arguments.openssl7z,
                                                    target_path, temp_path, caller_arguments)
            download_work.addTaskObject(download_task)
            unzip_task.addFunction(extract_task.do)
    qt_task.addFunction(download_work.run)
    qt_task.addFunction(unzip_task.do)
    return qt_task

def patch_qt(qt5_path):
    print("##### {0} #####".format("patch Qt"))
    qmake_binary = os.path.join(qt5_path, 'bin', 'qmake')
    # write qt.conf
    qtConfFile = open(os.path.join(qt5_path, 'bin', 'qt.conf'), "w")
    qtConfFile.write("[Paths]" + os.linesep)
    qtConfFile.write("Prefix=.." + os.linesep)
    qtConfFile.close()
    # fix rpaths
    if is_linux():
        handle_component_rpath(qt5_path, 'lib')
    print("##### {0} ##### ... done".format("patch Qt"))
    runCommand(qmake_binary + " -query", qt5_path)
