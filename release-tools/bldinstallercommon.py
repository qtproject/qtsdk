#!/usr/bin/env python
#############################################################################
##
## Copyright (C) 2012 Digia Plc and/or its subsidiary(-ies).
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

import errno
import fnmatch
import os
import platform
import re
import shutil
import subprocess
from subprocess import PIPE, STDOUT
import sys
import stat
import tarfile
import urllib
import urllib2
import zipfile
import string
import fileinput

# need to include this for win platforms as long path names
# cause problems
if platform.system().lower().startswith('win'):
    import win32api

SCRIPT_ROOT_DIR         = ''
PLATFORM_SUFFIX         = 'unknown'
IS_UNIX_PLATFORM        = False
IS_LINUX_PLATFORM       = False
IS_SOLARIS_PLATFORM     = False
IS_MAC_PLATFORM         = False
IS_WIN_PLATFORM         = False
DEBUG_RPATH             = False
MAX_DEBUG_PRINT_LENGTH  = 10000


###############################
# function
###############################
def init_common_module(root_path):
    global SCRIPT_ROOT_DIR
    SCRIPT_ROOT_DIR = root_path
    set_platform_specific_data()


###############################
# function
###############################
class head_request(urllib2.Request):
    def get_method(self):
        return 'HEAD'

def is_content_url_valid(url):
    # check first if the url points to file on local file system
    if (os.path.isfile(url)):
        return True
    # throws error if url does not point to valid object
    result = False
    try:
        response = urllib2.urlopen(head_request(url))
        result = True
    except Exception:
        pass

    return result;


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
        print '\n'


###############################
# function
###############################
def retrieve_url(url, savefile):
    try:
        savefile_tmp = savefile + '.tmp'
        urllib.urlcleanup()
        urllib.urlretrieve(url, savefile_tmp, reporthook=dlProgress)
        os.rename(savefile_tmp, savefile)
    except:
        exc = sys.exc_info()[0]
        print exc
        try:
            os.remove(savefile_tmp)
        except: #swallow, do not shadow actual error
            pass
        raise exc

###############################
# function
###############################
def set_platform_specific_data():
    global PLATFORM_SUFFIX
    global IS_UNIX_PLATFORM
    global IS_LINUX_PLATFORM
    global IS_SOLARIS_PLATFORM
    global IS_MAC_PLATFORM
    global IS_WIN_PLATFORM
    plat = platform.system().lower()
    if plat.startswith('win'):
        PLATFORM_SUFFIX = 'win'
        IS_WIN_PLATFORM = True
    elif plat.startswith('linux'):
        PLATFORM_SUFFIX = 'linux'
        IS_UNIX_PLATFORM = True
        IS_LINUX_PLATFORM = True
    elif plat.startswith('sun'):
        PLATFORM_SUFFIX = 'solaris'
        IS_UNIX_PLATFORM = True
        IS_SOLARIS_PLATFORM = True
    elif plat.startswith('darwin'):
        PLATFORM_SUFFIX = 'mac'
        IS_UNIX_PLATFORM = True
        IS_MAC_PLATFORM = True
    else:
        print '*** Unsupported platform, abort!'
        sys.exit(-1)


###############################
# function
###############################
def get_platform_suffix():
    return PLATFORM_SUFFIX


###############################
# function
###############################
def is_unix_platform():
    return IS_UNIX_PLATFORM

def is_linux_platform():
    return IS_LINUX_PLATFORM

def is_solaris_platform():
    return IS_SOLARIS_PLATFORM

def is_mac_platform():
    return IS_MAC_PLATFORM

def is_win_platform():
    return IS_WIN_PLATFORM


###############################
# function
###############################
def get_executable_suffix():
    if IS_WIN_PLATFORM:
        return '.exe'
    else:
        return ''


###############################
# function
###############################
def make_files_list(directory, rgxp):
    """Populate and return 'fileslist[]' with all files inside 'directory' matching 'regx'"""
    # if 'directory' is not a directory, exit with error
    if not os.path.isdir(directory):
        print '*** Error, Given path is not valid: ' + directory
        sys.exit(-1)
    regex = re.compile(rgxp)
    filelist = []
    for root, dirs, files in os.walk(directory):
        for name in files:
            if regex.search(name):
                path = os.path.join(root, name)
                filelist.append(path)

    return filelist[:]


###############################
# function
###############################
def delete_files_by_type_recursive(directory, rgxp):
    file_list = make_files_list(directory, rgxp)
    for item in file_list:
        os.remove(item)

###############################
# function
###############################
def findInSubdirectory(filename, subdirectory=''):
    if subdirectory:
        path = subdirectory
    else:
        path = os.getcwd()
    for root, dirs, names in os.walk(path):
        if filename in names:
            return os.path.join(root, filename)
    raise '*** Error! File not found!'


###############################
# function
###############################
def move_tree(srcdir, dstdir, pattern=None):
    # windows has length limit for path names so try to truncate them as much as possible
    global IS_WIN_PLATFORM
    if IS_WIN_PLATFORM:
        srcdir = win32api.GetShortPathName(srcdir)
        dstdir = win32api.GetShortPathName(dstdir)
    # dstdir must exist first
    srcnames = os.listdir(srcdir)
    for name in srcnames:
        srcfname = os.path.join(srcdir, name)
        if not srcfname:
            print '*** Fatal error! Unable to create source file path, too long path name!'
            sys.exit(-1)
        dstfname = os.path.join(dstdir, name)
        if not dstfname:
            print '*** Fatal error! Unable to create destination file path, too long path name!'
            sys.exit(-1)
        if is_win_platform():
            if len(srcfname) > 255:
                print 'given srcfname length (' + len(srcfname) + ') too long for Windows: ' + srcfname
                sys.exit(-1)
            if len(dstfname) > 255:
                print 'given dstfname length (' + len(dstfname) + ') too long for Windows: ' + dstfname
                sys.exit(-1)
        if os.path.isdir(srcfname) and not os.path.islink(srcfname):
            os.mkdir(dstfname)
            move_tree(srcfname, dstfname)
        elif pattern is None or fnmatch.fnmatch(name, pattern):
            os.rename(srcfname, dstfname)


###############################
# function
###############################
def copy_tree(source_dir, dest_dir):
    # windows has length limit for path names so try to truncate them as much as possible
    if IS_WIN_PLATFORM:
        source_dir = win32api.GetShortPathName(source_dir)
        dest_dir = win32api.GetShortPathName(dest_dir)
    src_files = os.listdir(source_dir)
    for file_name in src_files:
        full_file_name = os.path.join(source_dir, file_name)
        if not full_file_name:
            print '*** Fatal error! Unable to create source file path, too long path name!'
            sys.exit(-1)
        if is_win_platform():
            if len(full_file_name) > 255:
                print 'given full_file_name length (' + len(full_file_name) + ') too long for Windows: ' + full_file_name
                sys.exit(-1)
        if (os.path.isdir(full_file_name)):
            create_dirs(dest_dir + os.sep + file_name)
            copy_tree(full_file_name, dest_dir + os.sep + file_name)
        if (os.path.isfile(full_file_name)):
            shutil.copy(full_file_name, dest_dir)


###############################
# function
###############################
def handle_remove_readonly(func, path, exc):
  excvalue = exc[1]
  if func in (os.rmdir, os.remove) and excvalue.errno == errno.EACCES:
      os.chmod(path, stat.S_IRWXU| stat.S_IRWXG| stat.S_IRWXO) # 0777
      func(path)
  else:
      raise

def remove_tree(source_dir):
    if IS_WIN_PLATFORM:
        if os.path.exists(source_dir):
            source_dir = win32api.GetShortPathName(source_dir)
            cmd_args = ['rmdir', source_dir, '/S', '/Q']
            do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)
    else:
        #shutil.rmtree(source_dir)
        cmd_args = ['rm' , '-rf', source_dir]
        do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)


###############################
# function
###############################
# substitute all matches in files with replacement_string
def replace_in_files(filelist, regexp, replacement_string):
    regexp_compiled=re.compile(regexp)
    for xfile in filelist:
        replaceflag=0
        readlines=open(xfile,'r').readlines()
        listindex = -1
        for currentline in readlines:
            listindex = listindex + 1
            if regexp_compiled.search(currentline):
                # substitute
                f=re.sub(regexp,replacement_string,currentline)
                # update the whole file variable ('readlines')
                readlines[listindex] = f
                replaceflag=1
        # if some text was replaced overwrite the original file
        if replaceflag==1:
            # open the file for writting
            write_file=open(xfile,'w')
            # overwrite the file
            for line in readlines:
                write_file.write(line)
            # close the file
            write_file.close()


###############################
# function
###############################
def replace_in_text_files(root_directory, match_string, replacement_string, file_type_ignore_list):
    print '------------ replace_in_text_files ----------------'
    print '  root_directory:     ' + root_directory
    print '  match_string:       ' + match_string
    print '  replacement_string: ' + replacement_string
    pattern = re.compile(match_string)
    for root, dirs, files in os.walk(root_directory):
        for name in files:
            path = os.path.join(root, name)
            if not os.path.isdir(path) and not os.path.islink(path):
                if not (any(name.endswith(item) for item in file_type_ignore_list)):
                    readlines=open(path,'r').read()
                    if pattern.search(readlines):
                        print '---> Regexp match: ' + path
                        if is_text_file(path):
                            print '---> Replacing build path in: ' + path
                            print '--->         String to match: ' + match_string
                            print '--->             Replacement: ' + replacement_string
                            for line in fileinput.FileInput(path,inplace=1):
                                output1 = line.replace(match_string, replacement_string)
                                if line != output1:
                                    # we had a match
                                    print output1.rstrip('\n')
                                else:
                                    # no match so write original line back to file
                                    print line.rstrip('\n')
    print '--------------------------------------------------------------------'


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
        except:
            print('exception on %s!' % option)
            dict1[option] = None
    return dict1


###############################
# function
###############################
def dump_config(conf, name):
    # dump entire config file
    print '------------------------------'
    print '- Config: ' + name
    print '------------------------------'
    for section in conf.sections():
        print '[' + section + ']'
        for option in conf.options(section):
            print ' ', option, '=', conf.get(section, option)
    print '------------------------------'


###############################
# function
###############################
def create_dirs(path_to_be_created):
    if not os.path.exists(path_to_be_created):
        try:
            os.makedirs(path_to_be_created)
        except:
            print '*** Failed to create dir: ' + path_to_be_created
            sys.exit(-1)


###############################
# Function
###############################
def locate_executable(directory, file_name):
    for root, dirs, files in os.walk(directory):
        for basename in files:
            if fnmatch.fnmatch(basename, file_name):
                filename = os.path.join(root, basename)
                if is_executable(filename):
                    # return the first match
                    return filename
    print '*** Warning! Unable to locate: [' + file_name + '] from:' + directory
    return ''


###############################
# Function
###############################
def locate_directory(base_dir, dir_name):
    for root, dirs, files in os.walk(base_dir):
        for basename in dirs:
            if fnmatch.fnmatch(basename, dir_name):
                fulldirname = os.path.join(root, basename)
                # return the first match
                return fulldirname
    print '*** Warning! Unable to locate: [' + dir_name + '] from:' + base_dir
    return ''


###############################
# Function
###############################
def is_executable(path):
    plat = platform.system().lower()
    if IS_WIN_PLATFORM:
        if path.endswith('.exe') or path.endswith('.com'):
            return True
    elif IS_LINUX_PLATFORM:
        return (re.search(r':.* ELF',
                          subprocess.Popen(['file', '-L', path],
                                           stdout=subprocess.PIPE).stdout.read())
                is not None)
    elif IS_SOLARIS_PLATFORM:
        return (re.search(r':.* ELF',
                          subprocess.Popen(['file', '-dh', path],
                                           stdout=subprocess.PIPE).stdout.read())
                is not None)
    elif IS_MAC_PLATFORM:
        return (re.search(r'executable',
                          subprocess.Popen(['file', path],
                                           stdout=subprocess.PIPE).stdout.read())
                is not None)
    else:
        print '*** Error, is_executable not implemented yet!'
        sys.exit(-1)

    return False


###############################
# Function
###############################
# original snippet: http://code.activestate.com/recipes/173220-test-if-a-file-or-string-is-text-or-binary/

text_characters = "".join(map(chr, range(32, 127)) + list("\n\r\t\b"))
_null_trans     = string.maketrans("", "")

def is_text(s):
    if "\0" in s:
        return 0
    if not s:  # Empty files are considered text
        return 1
    # Get the non-text characters (maps a character to itself then
    # use the 'remove' option to get rid of the text characters.)
    t = s.translate(_null_trans, text_characters)
    # If more than 30% non-text characters, then
    # this is considered a binary file
    if len(t)/len(s) > 0.30:
        return 0
    return 1

def is_text_file(filename, blocksize = 512):
    return is_text(open(filename).read(blocksize))

###############################
# Function
###############################
def requires_rpath(file_path):
    if IS_WIN_PLATFORM:
        return False
    elif IS_LINUX_PLATFORM or IS_SOLARIS_PLATFORM:
        base = os.path.basename(file_path)
        filename, ext = os.path.splitext(base)
        # filter out some files from search, TODO
        m = re.match('\.o|\.h|\.png|\.htm|\.html|\.qml|\.qrc|\.jpg|\.svg|\.pro|\.pri|\.desktop|\.sci|\.txt|\.qdoc', ext)
        if m:
            return False
        if filename.lower() == 'qmake':
            return False
        elif ext.lower() == '.so':
            return True
        else:
            return is_executable(file_path)
    elif IS_MAC_PLATFORM:
        return False
    else:
        print '*** Unsupported platform!'
        sys.exit(-1)

    return False


###############################
# Function
###############################
def pathsplit(p, rest=[]):
    (h,t) = os.path.split(p)
    if len(h) < 1: return [t]+rest
    if len(t) < 1: return [h]+rest
    return pathsplit(h,[t]+rest)

def commonpath(l1, l2, common=[]):
    if len(l1) < 1: return (common, l1, l2)
    if len(l2) < 1: return (common, l1, l2)
    if l1[0] != l2[0]: return (common, l1, l2)
    return commonpath(l1[1:], l2[1:], common+[l1[0]])

def calculate_relpath(p1, p2):
    (common,l1,l2) = commonpath(pathsplit(p1), pathsplit(p2))
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
    if not (os.path.isfile(file_full_path)):
        print '*** Not a valid file: ' + file_full_path
        sys.exit(-1)

    bin_path    = os.path.dirname(file_full_path)
    path_to_lib = os.path.abspath(destination_lib_path)
    full_rpath = ''
    if path_to_lib == bin_path:
        full_rpath = '$ORIGIN'
    else:
        rp = calculate_relpath(bin_path, path_to_lib)
        full_rpath = '$ORIGIN' + os.sep + rp

    if DEBUG_RPATH:
        print '        ----------------------------------------'
        print '         RPath target folder: ' + path_to_lib
        print '         Bin file:            ' + file_full_path
        print '         Calculated RPath:    ' + full_rpath

    return full_rpath


##############################################################
# Handle the RPath in the given component files
##############################################################
def handle_component_rpath(component_root_path, destination_lib_path):
    print '        @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@'
    print '        Handle RPath'
    print ''
    print '        Component root path:  ' + component_root_path
    print '        Destination lib path: ' + destination_lib_path

    # initialize the file list
    fileslist = []
    # loop on all files
    for root, dirs, files in os.walk(component_root_path):
        for name in files:
            file_full_path = os.path.join(root, name)
            if not os.path.isdir(file_full_path) and not os.path.islink(file_full_path):
                if requires_rpath(file_full_path):
                    dst = os.path.normpath(component_root_path + os.sep + destination_lib_path)
                    rp = calculate_rpath(file_full_path, dst)
                    #print '        RPath value: [' + rp + '] for file: [' + file_full_path + ']'
                    cmd_args = ['chrpath', '-r', rp, file_full_path]
                    #force silent operation
                    do_execute_sub_process_get_std_out(cmd_args, SCRIPT_ROOT_DIR, True, False)


###############################
# function
###############################
def do_execute_sub_process(args, execution_path, abort_on_fail):
    print '      --------------------------------------------------------------------'
    print '      Executing:      [' + list_as_string(args) + ']'
    print '      Execution path: [' + execution_path + ']'
    print '      Abort on fail:  [' + str(abort_on_fail) + ']'
    return_code = -1
    try:
        os.chdir(execution_path)
        if IS_WIN_PLATFORM:
            theproc = subprocess.Popen(args, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=False)
        else:
            theproc = subprocess.Popen(args)
        output = theproc.communicate()[0]
        if theproc.returncode:
            return_code = theproc.returncode
            if output:
                output = output[len(output) - MAX_DEBUG_PRINT_LENGTH:] if len(output) > MAX_DEBUG_PRINT_LENGTH else output
                print output
            else:
                print '    Note, no output from the sub process!'
            print '*** Execution failed with code: %s' % str(theproc.returncode)
            if abort_on_fail:
                sys.exit(-1)
        print '      --------------------------------------------------------------------'
    except Exception:
        print sys.exc_info()
        if abort_on_fail:
            sys.exit(-1)
        else:
            pass

    os.chdir(SCRIPT_ROOT_DIR)
    return return_code


###############################
# function
###############################
def do_execute_sub_process_2(args, execution_path, abort_on_fail):
    print '      --------------------------------------------------------------------'
    print '      Executing:      [' + args + ']'
    print '      Execution path: [' + execution_path + ']'
    print '      Abort on fail:  [' + str(abort_on_fail) + ']'
    return_code = -1
    try:
        os.chdir(execution_path)
        theproc = subprocess.Popen(args, shell=True)
        output = theproc.communicate()[0]
        if theproc.returncode:
            return_code = theproc.returncode
            if output:
                output = output[len(output) - MAX_DEBUG_PRINT_LENGTH:] if len(output) > MAX_DEBUG_PRINT_LENGTH else output
                print output
            else:
                print '    Note, no output from the sub process!'
            print '*** Execution failed with code: %s' % str(theproc.returncode)
            if abort_on_fail:
                sys.exit(-1)
        print '      --------------------------------------------------------------------'
    except Exception:
        print sys.exc_info()
        if abort_on_fail:
            sys.exit(-1)
        else:
            pass

    os.chdir(SCRIPT_ROOT_DIR)
    return return_code


###############################
# function
###############################
def do_execute_sub_process_get_std_out(args, execution_path, abort_on_fail, print_debug=True):
    if print_debug:
        print '      --------------------------------------------------------------------'
        print '      Executing:      [' + list_as_string(args) + ']'
        print '      Execution path: [' + execution_path + ']'
        print '      Abort on fail:  [' + str(abort_on_fail) + ']'
    theproc = None
    output = ''
    try:
        os.chdir(execution_path)
        if IS_WIN_PLATFORM:
            theproc = subprocess.Popen(args, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=False)
        else:
            theproc = subprocess.Popen(args, shell=False, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
        output = theproc.communicate()[0]
        if theproc.returncode:
            if output:
                output = output[len(output) - MAX_DEBUG_PRINT_LENGTH:] if len(output) > MAX_DEBUG_PRINT_LENGTH else output
                print output
            else:
                print '    Note, no output from the sub process!'
            print '*** Execution failed with code: %s' % str(theproc.returncode)
            if abort_on_fail:
                sys.exit(-1)
        if print_debug:
            print '      --------------------------------------------------------------------'
    except Exception:
        print sys.exc_info()
        if abort_on_fail:
            sys.exit(-1)
        else:
            pass

    os.chdir(SCRIPT_ROOT_DIR)
    return output


###############################
# function
###############################
def clone_repository(repo_url, repo_branch_or_tag, destination_folder):
    print '--------------------------------------------------------------------'
    print 'Cloning repository: ' + repo_url
    print '        branch/tag: ' + repo_branch_or_tag
    print 'Dest:               ' + destination_folder
    print '--------------------------------------------------------------------'

    cmd_args = ['git', 'clone', '--depth', '0', repo_url, destination_folder]
    do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)

    cmd_args = ['git', 'checkout', repo_branch_or_tag]
    do_execute_sub_process(cmd_args, destination_folder, True)


###############################
# function
###############################
def extract_file(path, to_directory='.'):
    cmd_args = []
    if path.endswith('.zip'):
        cmd_args = ['7z', 'x', path]
    elif path.endswith('.tar'):
        cmd_args = ['tar', '-xzf', path]
    elif path.endswith('.tar.gz') or path.endswith('.tgz'):
        cmd_args = ['tar', '-xzf', path]
    elif path.endswith('.tar.bz2') or path.endswith('.tbz'):
        cmd_args = ['tar', '-xjf', path]
    elif path.endswith('.7z'):
        cmd_args = ['7z', 'x', path]
        # 7z does not have silent operation so we do it the hard way....
        do_execute_sub_process_get_std_out(cmd_args, to_directory, False)
        return True
    else:
        print 'Did not extract the file! Not archived or no appropriate extractor was found: ' + path
        return False

    do_execute_sub_process(cmd_args, to_directory, True)
    return True


###############################
# function
###############################
def list_as_string(argument_list):
    output= ' '.join(argument_list)
    return output

