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
import sys
import os
import re
import platform
import argparse
import multiprocessing
import bldinstallercommon
import shutil
import shlex
import ConfigParser
import urllib
import urlparse
import tarfile

LICENSE                                 = 'opensource'
SSH_COMMAND                             = 'ssh'
REPO_STAGING_SERVER                     = 'server'
REPO_STAGING_SERVER_UNAME               = 'username'
REPO_STAGING_SERVER_HOME                = ''
REPO_STAGING_SERVER_HOME_TOOLS          = 'qtsdk/release-tools'
SCRIPT_ROOT_DIR                         = os.path.dirname(os.path.realpath(__file__))
IFW_TOOLS_BASE_URL                      = ''
CONFIGURATIONS_FILE_BASE_DIR            = ''

REPO_STAGING_SERVER_TEST_REPO           = '/online_repo'
REPO_STAGING_SERVER_TEST_REPO_PENDING   = '/online_repo_pending'

PKG_SERVER_URL                          = ''
# search/replace tags in configuration files
GLOBAL_VERSION_TAG                      = '%GLOBAL_VERSION%'


# container for online repository build job parameters
class BuildJob:
    def __init__(self,
                 is_repo_job,
                 license,
                 node_name,
                 architecture,
                 version_number,
                 version_number_tag,
                 configurations_dir,
                 configurations_file,
                 ifw_tools,
                 substitution_list,
                 repo_qt_type,
                 repo_content_type,
                 repo_components_to_update,
                 repo_url_specifier
                ):
        self.is_repo_job                = is_repo_job
        self.license                    = license
        self.node_name                  = node_name
        self.architecture               = architecture
        self.version_number             = version_number
        self.version_number_tag         = version_number_tag
        self.configurations_dir         = configurations_dir
        self.configurations_file        = configurations_file
        self.ifw_tools                  = ifw_tools
        self.substitution_arg_list      = []
        self.repo_qt_type               = repo_qt_type
        self.repo_content_type          = repo_content_type
        self.repo_components_to_update  = repo_components_to_update
        self.repo_url_specifier         = repo_url_specifier
        self.format_substitution_list(substitution_list)

    # format substitution list so that it can be used by create_installer.py
    def format_substitution_list(self, substitution_list):
        item_list = substitution_list.split(',')
        for item in item_list:
            temp = item.replace(' ', '')
            self.substitution_arg_list.append('--add-substitution=' + temp)

    # print some verbose
    def print_data(self):
        print('==============================')
        print('[{0}]'.format(self.node_name))
        print(self.license)
        print(self.architecture)
        print(self.version_number)
        print(self.version_number_tag)
        print(self.configurations_dir)
        print(self.configurations_file)
        print(self.ifw_tools)
        print(self.substitution_arg_list)
        if self.is_repo_job:
            print(self.repo_qt_type)
            print(self.repo_content_type)
            print(self.repo_components_to_update)
            print(self.repo_url_specifier)

    # validate content
    def validate(self):
        if not self.node_name:
            print('*** Fatal error! <node_name> not defined for build job?')
            sys.exit(-1)
        if not self.license:
            print('*** Fatal error! <license> not defined for {0}'.format(self.node_name))
            sys.exit(-1)
        if not self.version_number:
            print('*** Fatal error! <version_number> not defined for {0}'.format(self.node_name))
            sys.exit(-1)
        if not self.configurations_dir:
            print('*** Fatal error! <configurations_dir> not defined for {0}'.format(self.node_name))
            sys.exit(-1)
        if not self.configurations_file:
            print('*** Fatal error! <configurations_file> not defined for {0}'.format(self.node_name))
            sys.exit(-1)
        if not self.ifw_tools:
            print('*** Fatal error! <ifw_tools> not defined for {0}'.format(self.node_name))
            sys.exit(-1)
        if self.is_repo_job:
            if not self.repo_content_type:
                print('*** Fatal error! <repo_content_type> not defined for {0}'.format(self.node_name))
                sys.exit(-1)
            if not self.repo_content_type:
                print('*** Fatal error! <repo_content_type> not defined for {0}'.format(self.node_name))
                sys.exit(-1)
            if not self.repo_components_to_update:
                print('*** Fatal error! <repo_components_to_update> not defined for {0}'.format(self.node_name))
                sys.exit(-1)
            if not self.repo_url_specifier:
                print('*** Fatal error! <repo_url_specifier> not defined for {0}'.format(self.node_name))
                sys.exit(-1)
        # all ok
        return True

    def get_package_type(self):
        items = self.node_name.split('.')
        if len(items) >= 6:
            return items[5]

def preformat_substitution_list(arg_substitution_list, global_version, global_version_tag):
    version = global_version
    if global_version_tag:
        version = version + '-' + global_version_tag
    temp = arg_substitution_list.replace(GLOBAL_VERSION_TAG, version)
    return temp


def is_valid_job_type(job_type_specifier):
    if (job_type_specifier == 'repository'):
        return True
    if (job_type_specifier == 'offline'):
        return True
    if (job_type_specifier == 'online'):
        return True
    return False


# parse build jobs for given platform and architecture
#<branch>.<qt_version>.<offline/repository>.<host_os>.<architecture>.<package_type>
def get_job_list(conf_file, job_type_specifier, license, qt_type, branch, platform, arch, conf_file_base_dir, ifw_base_url, global_version, global_version_tag):
    if not os.path.isfile(conf_file):
        print('*** Fatal error! Given file does not exist: {0}'.format(conf_file))
        sys.exit(-1)
    parser = ConfigParser.ConfigParser()
    parser.readfp(open(conf_file))
    # validate job type
    if not is_valid_job_type(job_type_specifier):
        print('*** Fatal error! Unsupported job type specifier given {0}'.format(job_type_specifier))
        sys.exit(-1)
    # determine which ifw tools to use (which platform)
    ifw_tools = bldinstallercommon.safe_config_key_fetch(parser, 'ifwtools', platform + '-' + arch)
    if not ifw_tools:
        print('*** Fatal error! Unable to find ifw tools for {0}'.format(platform + '-' + arch))
        sys.exit(-1)
    ifw_tools_url = urlparse.urljoin(ifw_base_url, ifw_tools)
    # check if repository build job
    is_repo_job = False
    if job_type_specifier == 'repository':
        is_repo_job = True
    # parse
    job_list = []
    for s in parser.sections():
        section_parts = s.split('.')
        if (len(section_parts) < 5):
            continue
        if (section_parts[0] == branch and
            section_parts[2] == job_type_specifier and
            section_parts[3] == platform and
            section_parts[4] == arch):
            # parse from conf file
            version_number = bldinstallercommon.safe_config_key_fetch(parser, s, 'version_number')
            if not version_number:
                version_number = global_version
            version_number_tag = bldinstallercommon.safe_config_key_fetch(parser, s, 'version_number_tag')
            if not version_number_tag:
                version_number_tag = global_version_tag
            arg_configurations_file = bldinstallercommon.safe_config_key_fetch(parser, s, 'arg_configurations_file')
            if not arg_configurations_file:
                print('*** Fatal error! Configuration file not defined for {0}'.format(s))
                sys.exit(-1)
            arg_substitution_list = bldinstallercommon.safe_config_key_fetch(parser, s, 'arg_substitution_list')
            arg_substitution_list = preformat_substitution_list(arg_substitution_list, global_version, global_version_tag)
            repo_content_type           = ''
            repo_components_to_update   = ''
            repo_url_specifier          = ''
            # if online repo job
            if job_type_specifier == 'repository':
                repo_content_type = bldinstallercommon.safe_config_key_fetch(parser, s, 'repo_content_type')
                if not repo_content_type:
                    print('*** Fatal error! <repo_content_type> not defined for {0}'.format(s))
                    sys.exit(-1)
                repo_components_to_update = bldinstallercommon.safe_config_key_fetch(parser, s, 'repo_components_to_update')
                if not repo_components_to_update:
                    print('*** Fatal error! <repo_components_to_update> not defined for {0}'.format(s))
                    sys.exit(-1)
                repo_url_specifier = bldinstallercommon.safe_config_key_fetch(parser, s, 'repo_url_specifier')
                if not repo_url_specifier:
                    print('*** Fatal error! <repo_url_specifier> not defined for {0}'.format(s))
                    sys.exit(-1)
            # determine full path for the conf file
            full_conf_file_path = os.path.join(conf_file_base_dir, arg_configurations_file)
            # create build job
            job = BuildJob(is_repo_job, license, s, arch, version_number, version_number_tag, conf_file_base_dir, full_conf_file_path, ifw_tools_url, arg_substitution_list, qt_type, repo_content_type, repo_components_to_update, repo_url_specifier)
            if (job.validate()):
                job_list.append(job)
    return job_list


# parse online repository build jobs for given platform and architecture
#<branch>.<qt_version>.<offline/repository>.<host_os>.<architecture>.<package_type>
def get_repo_job_list(conf_file, license, qt_type, branch, platform, arch, conf_file_base_dir, ifw_base_url, global_version, global_version_tag):
    return get_job_list(conf_file, 'repository', license, qt_type, branch, platform, arch, conf_file_base_dir, ifw_base_url, global_version, global_version_tag)


# parse offline installer build jobs for given platform and architecture
#<branch>.<qt_version>.<offline/repository>.<host_os>.<architecture>.<package_type>
def get_offline_job_list(conf_file, license, qt_type, branch, platform, arch, conf_file_base_dir, ifw_base_url, global_version, global_version_tag):
    return get_job_list(conf_file, 'offline', license, qt_type, branch, platform, arch, conf_file_base_dir, ifw_base_url, global_version, global_version_tag)

# parse online installer build jobs for given platform and architecture
#<branch>.<qt_version>.<offline/repository>.<host_os>.<architecture>.<package_type>
def get_online_job_list(conf_file, license, qt_type, branch, platform, arch, conf_file_base_dir, ifw_base_url, global_version, global_version_tag):
    return get_job_list(conf_file, 'online', license, qt_type, branch, platform, arch, conf_file_base_dir, ifw_base_url, global_version, global_version_tag)


# execute
# - online installer build(s)
def handle_online_installer_build(conf_file, license, branch, platform, arch, packages_base_url):
    if not os.path.isfile(conf_file):
        print('*** Fatal error! Given file does not exist: {0}'.format(conf_file))
        sys.exit(-1)
    init_env()
    release_tools_dir   = SCRIPT_ROOT_DIR
    conf_file_base_dir  = CONFIGURATIONS_FILE_BASE_DIR
    ifw_base_url        = IFW_TOOLS_BASE_URL
    # parse conf file
    parser = ConfigParser.ConfigParser()
    parser.readfp(open(conf_file))
    section_name        = branch + '.' + 'global'
    global_qt_type      = bldinstallercommon.safe_config_key_fetch(parser, section_name, 'qt_type')
    global_version      = bldinstallercommon.safe_config_key_fetch(parser, section_name, 'version')
    global_version_tag  = bldinstallercommon.safe_config_key_fetch(parser, section_name, 'version_tag')
    if not global_version:
        print('*** Fatal error! Invalid values in {0} -> {1}'.format(conf_file, section_name))
        sys.exit(-1)
    # parse build jobs
    job_list = get_online_job_list(conf_file, license, global_qt_type, branch, platform, arch, conf_file_base_dir, ifw_base_url, global_version, global_version_tag)
    if (len(job_list) == 0):
        print('*** Fatal error! No online installer build jobs found. Probably an error?'.format(conf_file, section_name))
        sys.exit(-1)
    # handle build jobs
    for job in job_list:
        create_online_installer(job, packages_base_url)


# execute
# - offline installer build(s)
def handle_offline_installer_build(conf_file, license, branch, platform, arch, packages_base_url):
    if not os.path.isfile(conf_file):
        print('*** Fatal error! Given file does not exist: {0}'.format(conf_file))
        sys.exit(-1)
    init_env()
    release_tools_dir   = SCRIPT_ROOT_DIR
    conf_file_base_dir  = CONFIGURATIONS_FILE_BASE_DIR
    ifw_base_url        = IFW_TOOLS_BASE_URL
    # parse conf file
    parser = ConfigParser.ConfigParser()
    parser.readfp(open(conf_file))
    section_name        = branch + '.' + 'global'
    global_qt_type      = bldinstallercommon.safe_config_key_fetch(parser, section_name, 'qt_type')
    global_version      = bldinstallercommon.safe_config_key_fetch(parser, section_name, 'version')
    global_version_tag  = bldinstallercommon.safe_config_key_fetch(parser, section_name, 'version_tag')
    if not global_version:
        print('*** Fatal error! Invalid values in {0} -> {1}'.format(conf_file, section_name))
        sys.exit(-1)
    # parse build jobs
    job_list = get_offline_job_list(conf_file, license, global_qt_type, branch, platform, arch, conf_file_base_dir, ifw_base_url, global_version, global_version_tag)
    if (len(job_list) == 0):
        print('*** Fatal error! No offline build jobs found. Probably an error?'.format(conf_file, section_name))
        sys.exit(-1)
    # handle build jobs
    for job in job_list:
        create_offline_installer(job, packages_base_url)


# helper function/wrapper to create offline installer
def create_offline_installer(job, packages_base_url):
    cmd_args = ['python','-u','create_installer.py']
    cmd_args = cmd_args + ['-c', job.configurations_dir]
    cmd_args = cmd_args + ['-f', job.configurations_file]
    cmd_args = cmd_args + ['-o']
    cmd_args = cmd_args + ['-l', job.license]
    arch_naming = job.architecture
    package_type = job.get_package_type()
    if package_type:
        arch_naming = arch_naming + '-' + package_type
    cmd_args = cmd_args + ['-a', arch_naming]
    cmd_args = cmd_args + ['--version-number=' + job.version_number]
    cmd_args = cmd_args + ['--version-tag=' + job.version_number_tag]
    cmd_args = cmd_args + ['-u', urlparse.urljoin(packages_base_url, job.license)]
    cmd_args = cmd_args + ['--ifw-tools=' + job.ifw_tools]
    if (len(job.substitution_arg_list) > 0):
        for item in job.substitution_arg_list:
            cmd_args = cmd_args + [item]
    # execute
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)


# helper function/wrapper to create online installer
def create_online_installer(job, packages_base_url):
    cmd_args = ['python','-u','create_installer.py']
    cmd_args = cmd_args + ['-c', job.configurations_dir]
    cmd_args = cmd_args + ['-f', job.configurations_file]
    cmd_args = cmd_args + ['-O']
    cmd_args = cmd_args + ['-l', job.license]
    arch_naming = job.architecture
    package_type = job.get_package_type()
    if package_type:
        arch_naming = arch_naming + '-' + package_type
    cmd_args = cmd_args + ['-a', arch_naming]
    cmd_args = cmd_args + ['--version-number=' + job.version_number]
    cmd_args = cmd_args + ['--version-tag=' + job.version_number_tag]
    cmd_args = cmd_args + ['-u', urlparse.urljoin(packages_base_url, job.license)]
    cmd_args = cmd_args + ['--ifw-tools=' + job.ifw_tools]
    if (len(job.substitution_arg_list) > 0):
        for item in job.substitution_arg_list:
            cmd_args = cmd_args + [item]
    # execute
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)


# execute:
# - online reposiory build
# - upload repository into test server
# - update existing repository at test server with new content
def handle_repo_build(conf_file, license, branch, platform, arch, packages_base_url):
    if not os.path.isfile(conf_file):
        print('*** Fatal error! Given file does not exist: {0}'.format(conf_file))
        sys.exit(-1)
    init_env()
    release_tools_dir   = SCRIPT_ROOT_DIR
    conf_file_base_dir  = CONFIGURATIONS_FILE_BASE_DIR
    ifw_base_url        = IFW_TOOLS_BASE_URL
    # init repo dirs
    init_repositories(conf_file, branch, license)
    # parse conf file
    parser = ConfigParser.ConfigParser()
    parser.readfp(open(conf_file))
    section_name = branch + '.' + 'global'
    global_qt_type                     = bldinstallercommon.safe_config_key_fetch(parser, section_name, 'qt_type')
    global_version                     = bldinstallercommon.safe_config_key_fetch(parser, section_name, 'version')
    global_version_tag                 = bldinstallercommon.safe_config_key_fetch(parser, section_name, 'version_tag')
    if not global_version:
        print('*** Fatal error! Invalid values in {0} -> {1}'.format(conf_file, section_name))
        sys.exit(-1)
    # parse build jobs
    repo_job_list = get_repo_job_list(conf_file, license, global_qt_type, branch, platform, arch, conf_file_base_dir, ifw_base_url, global_version, global_version_tag)
    if (len(repo_job_list) == 0):
        print('*** Fatal error! No repository build jobs found. Probably an error?'.format(conf_file, section_name))
        sys.exit(-1)
    # handle repo build jobs
    for job in repo_job_list:
        create_online_repository(job, packages_base_url)
        # determine testination path on test server
        dest_path_repository, dest_path_pkg = generate_repo_dest_path_pending(job)
        # copy repo content to test server
        source_path_repository  = os.path.join(release_tools_dir, 'repository')
        source_path_pkg         = os.path.join(release_tools_dir, 'pkg')
        push_online_repository(REPO_STAGING_SERVER, REPO_STAGING_SERVER_UNAME, source_path_repository, dest_path_repository)
        push_online_repository(REPO_STAGING_SERVER, REPO_STAGING_SERVER_UNAME, source_path_pkg, dest_path_pkg)
        # remove local repository and pkg directories
        bldinstallercommon.remove_tree(source_path_repository)
        bldinstallercommon.remove_tree(source_path_pkg)
        # update repo in testing area
        update_online_repo(job)


# helper function to create online repository
def create_online_repository(build_job, packages_base_url):
    cmd_args = ['python','-u', 'create_installer.py', \
                '-c', build_job.configurations_dir, \
                '-f', build_job.configurations_file, \
                '--create-repo', \
                '-l', build_job.license, \
                '--version-number=' + build_job.version_number, \
                '-u', urlparse.urljoin(packages_base_url, build_job.license), \
                '--ifw-tools='+ build_job.ifw_tools]
    if (len(build_job.substitution_arg_list) > 0):
        for item in build_job.substitution_arg_list:
            cmd_args = cmd_args + [item]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)


# push online repository into remote server
def push_online_repository(server_addr, username, what_to_copy, where_to_copy):
    # tar contents to be transferred
    filename = os.path.join(SCRIPT_ROOT_DIR, 'repo.tar')
    print('filename: {0}'.format(filename))
    tar = tarfile.open(filename, "w")
    tar.add(what_to_copy, arcname="")
    tar.close()
    # transfer
    destination  = username + '@' + server_addr + ':' + where_to_copy + '/'
    cmd_args = [REMOTE_COPY_COMMAND, filename, destination]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)
    # delete local tar file
    os.remove(filename)
    # extract remote tar file
    cmd_args = [SSH_COMMAND, '-t', '-t', username + '@' + server_addr, 'tar', '-C', where_to_copy, '-xf', where_to_copy + '/' + 'repo.tar']
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)
    # delete remote tar file
    cmd_args = [SSH_COMMAND, '-t', '-t', username + '@' + server_addr, 'rm', '-f', where_to_copy + '/' + 'repo.tar']
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)


# init online repository directory structure at remote server
def init_repositories(conf_file, branch, license):
    if not os.path.isfile(conf_file):
        print('*** Fatal error! Given file does not exist: {0}'.format(conf_file))
        sys.exit(-1)
    init_env()
    parser = ConfigParser.ConfigParser()
    parser.readfp(open(conf_file))
    qt_type = bldinstallercommon.safe_config_key_fetch(parser, branch + '.' + 'global', 'qt_type')
    repo_content_type = bldinstallercommon.safe_config_key_fetch(parser, branch + '.' + 'global', 'repo_content_type')
    if not repo_content_type:
        print('*** Fatal error! Invalid values in {0} -> {1} missing?'.format(branch + '.' + 'global', 'repo_content_type'))
        sys.exit(-1)
    url_list = []
    for s in parser.sections():
        section_parts = s.split('.')
        if (len(section_parts) <= 2):
            continue
        if not (section_parts[0] == branch):
            continue
        if (section_parts[2] == 'repository'):
            repo_url_specifier = bldinstallercommon.safe_config_key_fetch(parser, s, 'repo_url_specifier')
            if not repo_url_specifier:
                print('*** Fatal error! Empty value in repo_url_specifier: {0}'.format(s))
                sys.exit(-1)
            url_list.append(repo_url_specifier)
    server_addr = REPO_STAGING_SERVER_UNAME + '@' + REPO_STAGING_SERVER
    # test area
    base_path_testing = os.path.join(REPO_STAGING_SERVER_TEST_REPO, license)
    create_online_repo_paths(server_addr, base_path_testing, [], url_list)
    # pending (merge) area
    base_path_pending = os.path.join(REPO_STAGING_SERVER_TEST_REPO_PENDING, license, repo_content_type)
    # delete old pending material first from pending area
    content_to_be_deleted = base_path_pending + '/*'
    delete_online_repo_paths(server_addr, content_to_be_deleted)
    # create clean dir structure in pending area
    create_online_repo_paths(server_addr, base_path_pending,  ['online_repository', 'pkg'], url_list)


# helper function to create remote directories
def create_remote_dirs(server, dir_path):
    cmd_args = [SSH_COMMAND, '-t', '-t', server, 'mkdir -p' ,dir_path]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)


# helper function to create remote directoriesinux_x64/desktop/qt5
def create_online_repo_paths(server_addr, base_path, suffix_list, url_list):
    repo_path_list = generate_online_repo_paths(base_path, suffix_list, url_list)
    for item in repo_path_list:
        print('Creating remote directory: {0}'.format(item))
        create_remote_dirs(server_addr, item)


# helper function to delete online repository directories on remote server
def delete_online_repo_paths(server_addr, path_to_be_deleted):
    cmd_args = [SSH_COMMAND, '-t', '-t', server_addr, 'rm -rf', path_to_be_deleted]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)


# helper function to generate correct path structure for online repos
def generate_online_repo_paths(base_path, suffix_list, url_list):
    repo_path_list = []
    for item in url_list:
        if not suffix_list:
            path_repo = os.path.join(base_path, 'qtsdkrepository', item)
            repo_path_list.append(path_repo)
        else:
            for suffix in suffix_list:
                path_repo = os.path.join(base_path, 'qtsdkrepository', item, suffix)
                repo_path_list.append(path_repo)
    return repo_path_list


# helper function to generate correct path structure for pending area
def generate_repo_dest_path_pending(repo_job):
    dest_path_base = os.path.join(REPO_STAGING_SERVER_TEST_REPO_PENDING, repo_job.license, repo_job.repo_content_type, 'qtsdkrepository', repo_job.repo_url_specifier)
    dest_path_repository = os.path.join(dest_path_base, 'online_repository')
    dest_path_pkg = os.path.join(dest_path_base, 'pkg')
    return dest_path_repository, dest_path_pkg


# execute online repository update
def update_online_repo(job):
    server_addr = REPO_STAGING_SERVER_UNAME + '@' + REPO_STAGING_SERVER
    staging_server_ifw_tools = 'installer-framework-build-linux-x64.7z'
    script = os.path.join(REPO_STAGING_SERVER_HOME_TOOLS, 'update_repository.py')
    repogen_tools = os.path.join(REPO_STAGING_SERVER_HOME, staging_server_ifw_tools)
    # determine paths on test server
    source_repo, source_pkg = generate_repo_dest_path_pending(job)
    # determine target repo
    target_repo = os.path.join(REPO_STAGING_SERVER_TEST_REPO, job.license, 'qtsdkrepository', job.repo_url_specifier)
    repo_components_to_update = job.repo_components_to_update
    cmd_args = [SSH_COMMAND, '-t', '-t', server_addr]
    cmd_args = cmd_args + ['python', script]
    cmd_args = cmd_args + ['--repogen_tools=' + repogen_tools]
    cmd_args = cmd_args + ['--source_pkg=' + source_pkg]
    cmd_args = cmd_args + ['--source_repo=' + source_repo]
    cmd_args = cmd_args + ['--target_repo=' + target_repo]
    cmd_args = cmd_args + ['--components_to_update=' + repo_components_to_update]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)


# init environment
def init_env():
    global REPO_STAGING_SERVER
    global REPO_STAGING_SERVER_UNAME
    global LICENSE
    global PKG_SERVER_URL
    global REPO_STAGING_SERVER_HOME
    global REPO_STAGING_SERVER_HOME_TOOLS
    global SSH_COMMAND
    global IFW_TOOLS_BASE_URL
    global CONFIGURATIONS_FILE_BASE_DIR
    global REMOTE_COPY_COMMAND
    REPO_STAGING_SERVER             = os.environ['PKG_STAGING_SERVER']
    REPO_STAGING_SERVER_UNAME       = os.environ['PKG_STAGING_SERVER_UNAME']
    LICENSE                         = os.environ['LICENSE']
    PKG_SERVER_URL                  = os.environ['PKG_SERVER_URL']
    REPO_STAGING_SERVER_HOME        = os.environ['REPO_STAGING_SERVER_HOME']
    REPO_STAGING_SERVER_HOME_TOOLS  = os.path.join(REPO_STAGING_SERVER_HOME, REPO_STAGING_SERVER_HOME_TOOLS)
    IFW_TOOLS_BASE_URL              = os.environ['IFW_TOOLS_BASE_URL']
    CONFIGURATIONS_FILE_BASE_DIR    = os.environ['CONFIGURATIONS_FILE_BASE_DIR']
    REMOTE_COPY_COMMAND             = os.environ['REMOTE_COPY_COMMAND']
    print('Staging server: {0}'.format(REPO_STAGING_SERVER))
    print('Staging server uname: {0}'.format(REPO_STAGING_SERVER_UNAME))
    print('License: {0}'.format(LICENSE))
    print('Packages server base URL: {0}'.format(PKG_SERVER_URL))
    print('Staging server home: {0}'.format(REPO_STAGING_SERVER_HOME))
    print('Staging server tools dir: {0}'.format(REPO_STAGING_SERVER_HOME_TOOLS))
    print('IFW tools base url: {0}'.format(IFW_TOOLS_BASE_URL))
    print('Configurations file base dir: {0}'.format(CONFIGURATIONS_FILE_BASE_DIR))
    bldinstallercommon.init_common_module(SCRIPT_ROOT_DIR)
    if bldinstallercommon.is_win_platform():
        SSH_COMMAND = '%SSH%'


