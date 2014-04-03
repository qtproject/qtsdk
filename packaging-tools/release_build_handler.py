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
import bldinstallercommon
import pkg_constants
import ConfigParser
import urlparse
import tarfile

INIT_DONE                               = False
SSH_COMMAND                             = 'ssh'
REMOTE_COPY_COMMAND                     = 'scp'
REPO_STAGING_SERVER                     = 'server'
REPO_STAGING_SERVER_UNAME               = 'username'
REPO_STAGING_SERVER_HOME                = ''
REPO_STAGING_SERVER_HOME_TOOLS          = 'qtsdk/packaging-tools'
SCRIPT_ROOT_DIR                         = os.path.dirname(os.path.realpath(__file__))
IFW_TOOLS_BASE_URL                      = ''
CONFIGURATIONS_FILE_BASE_DIR            = ''

REPOSITORY_BASE_NAME                    = 'qtsdkrepository'

REPO_STAGING_SERVER_TEST_REPO           = '/online_repo'
REPO_STAGING_SERVER_TEST_REPO_PENDING   = '/online_repo_pending'
REPO_STAGING_SERVER_TEST_REPO_DIST_WORK = '/online_repo_dist_update_work'

PROD_USER                               = ''
PROD_ADDR                               = ''
PROD_SRV_REPO_BASE_PATH                 = ''
PROD_SRV_REPO_PENDING_AREA_DIR          = ''

PKG_SERVER_URL                          = ''
# search/replace tags in configuration files
GLOBAL_VERSION_TAG                      = '%GLOBAL_VERSION%'


# container for online repository build job parameters
class BuildJob:
    def __init__(self,
                 is_repo_job,
                 license_type,
                 node_name,
                 architecture,
                 version_number,
                 version_number_tag,
                 configurations_dir,
                 configurations_file,
                 ifw_tools,
                 substitution_list,
                 repo_content_type,
                 repo_components_to_update,
                 repo_url_specifier,
                 installer_name,
                 rta_keys
                ):
        self.is_repo_job                = is_repo_job
        self.license                    = license_type
        self.node_name                  = node_name
        self.architecture               = architecture
        self.version_number             = version_number
        self.version_number_tag         = version_number_tag
        self.configurations_dir         = configurations_dir
        self.configurations_file        = configurations_file
        self.ifw_tools                  = ifw_tools
        self.substitution_arg_list      = []
        self.repo_content_type          = repo_content_type
        self.repo_components_to_update  = repo_components_to_update
        self.repo_url_specifier         = repo_url_specifier
        self.installer_name             = preformat_global_version_number(installer_name, version_number, version_number_tag)
        self.rta_key_list               = rta_keys.replace(' ', '')
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
            print(self.repo_content_type)
            print(self.repo_components_to_update)
            print(self.repo_url_specifier)
        print('')

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


def preformat_global_version_number(arg_substitution_list, global_version, global_version_tag):
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
def get_job_list(conf_file, job_type_specifier, license_type, branch, platform, arch, conf_file_base_dir, ifw_base_url, global_version, global_version_tag):
    print('Get [{0}] build job list for: {1}'.format(job_type_specifier, platform + '-' + arch))
    if not os.path.isfile(conf_file):
        print('*** Fatal error! Given file does not exist: {0}'.format(conf_file))
        sys.exit(-1)
    # ensure the string ends with '/'
    if not ifw_base_url.endswith('/'):
        ifw_base_url += '/'
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
            # for triggering rta later on if specified
            rta_key_list = bldinstallercommon.safe_config_key_fetch(parser, s, 'rta_key_list')
            # preferred installer name
            installer_name = bldinstallercommon.safe_config_key_fetch(parser, s, 'installer_name')
            arg_substitution_list = bldinstallercommon.safe_config_key_fetch(parser, s, 'arg_substitution_list')
            arg_substitution_list = preformat_global_version_number(arg_substitution_list, global_version, global_version_tag)
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
            job = BuildJob(is_repo_job, license_type, s, arch, version_number, version_number_tag, conf_file_base_dir, full_conf_file_path, ifw_tools_url, arg_substitution_list, repo_content_type, repo_components_to_update, repo_url_specifier, installer_name, rta_key_list)
            if (job.validate()):
                job_list.append(job)
    return job_list


# parse online repository build jobs for given platform and architecture
#<branch>.<qt_version>.<offline/repository>.<host_os>.<architecture>.<package_type>
def get_repo_job_list(conf_file, license_type, branch, platform, arch, conf_file_base_dir, ifw_base_url, global_version, global_version_tag):
    return get_job_list(conf_file, 'repository', license_type, branch, platform, arch, conf_file_base_dir, ifw_base_url, global_version, global_version_tag)


# execute
# - online installer build(s)
def handle_installer_build(conf_file, installer_type, license_type, branch, platform, arch, packages_base_url):
    if not os.path.isfile(conf_file):
        print('*** Fatal error! Given file does not exist: {0}'.format(conf_file))
        sys.exit(-1)
    init_env()
    conf_file_base_dir  = CONFIGURATIONS_FILE_BASE_DIR
    ifw_base_url        = IFW_TOOLS_BASE_URL
    # parse conf file
    parser = ConfigParser.ConfigParser()
    parser.readfp(open(conf_file))
    section_name        = branch + '.' + 'global'
    global_version      = bldinstallercommon.safe_config_key_fetch(parser, section_name, 'version')
    global_version_tag  = bldinstallercommon.safe_config_key_fetch(parser, section_name, 'version_tag')
    if not global_version:
        print('*** Fatal error! Invalid values in {0} -> {1}'.format(conf_file, section_name))
        sys.exit(-1)
    # parse build jobs
    job_list = get_job_list(conf_file, installer_type, license_type, branch, platform, arch, conf_file_base_dir, ifw_base_url, global_version, global_version_tag)
    if (len(job_list) == 0):
        print('*** Fatal error! No [{0}] installer build jobs found from: {1}. Probably an error?'.format(installer_type, conf_file))
        sys.exit(-1)
    installer_output_dir = os.path.join(SCRIPT_ROOT_DIR, 'installer_output')
    rta_descr_output_dir = os.path.join(SCRIPT_ROOT_DIR, pkg_constants.RTA_DESCRIPTION_FILE_DIR_NAME)
    bldinstallercommon.create_dirs(rta_descr_output_dir)
    # create rta description file
    architecture = bldinstallercommon.get_architecture()
    plat_suffix = bldinstallercommon.get_platform_suffix()
    rta_description_file_name = os.path.join(rta_descr_output_dir, pkg_constants.RTA_DESCRIPTION_FILE_NAME_BASE + '-' + plat_suffix + '-' + architecture + '.txt')
    # handle build jobs
    for job in job_list:
        # create installer
        type_arg = '--online'  if 'online' in installer_type.lower() else '--offline'
        creation_ok = create_installer(job, packages_base_url, type_arg)
        # write the rta description file only if installer creation was ok
        if (creation_ok):
            rta_description_file = open(rta_description_file_name, 'a')
            rta_description_file.write(job.installer_name + ' ' + job.rta_key_list + '\n')
            rta_description_file.close()
    # if "/installer_output" directory is empty -> error
    if not os.listdir(installer_output_dir):
        print('*** Fatal error! No installers generated into: {0}'.format(installer_output_dir))
        sys.exit(-1)


# helper function/wrapper to create online installer
def create_installer(job, packages_base_url, installer_type):
    # ensure the string ends with '/'
    if not packages_base_url.endswith('/'):
        packages_base_url += '/'
    job.print_data()
    cmd_args = ['python', '-u','create_installer.py']
    cmd_args = cmd_args + ['-c', job.configurations_dir]
    cmd_args = cmd_args + ['-f', job.configurations_file]
    cmd_args = cmd_args + [installer_type]
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
    cmd_args = cmd_args + ['--preferred-installer-name=' + job.installer_name]
    if (len(job.substitution_arg_list) > 0):
        for item in job.substitution_arg_list:
            cmd_args = cmd_args + [item]
    # execute, do not bail out if installer job fails
    subprocess_exec_stataus = False
    try:
        bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)
        subprocess_exec_stataus = True
    except:
        # catch any interrupt into installer creation, we assume the operation failed
        subprocess_exec_stataus = False
    return subprocess_exec_stataus

# execute:
# - online reposiory build
# - upload repository into test server
# - update existing repository at test server with new content
def handle_repo_build(conf_file, license_type, branch, platform, arch, packages_base_url, update_staging_repo, update_production_repo):
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
    section_name = branch + '.' + 'global'
    global_version     = bldinstallercommon.safe_config_key_fetch(parser, section_name, 'version')
    global_version_tag = bldinstallercommon.safe_config_key_fetch(parser, section_name, 'version_tag')
    if not global_version:
        print('*** Fatal error! Invalid values in {0} -> {1}'.format(conf_file, section_name))
        sys.exit(-1)
    # parse build jobs
    repo_job_list = get_repo_job_list(conf_file, license_type, branch, platform, arch, conf_file_base_dir, ifw_base_url, global_version, global_version_tag)
    if (len(repo_job_list) == 0):
        print('*** Fatal error! No repository build jobs found. Probably an error?'.format(conf_file, section_name))
        sys.exit(-1)
    # init repo dirs
    init_repositories(repo_job_list)
    # is this snapshot build? Then enable component version number forced update
    forced_version_number_bump = False
    if update_staging_repo and not update_production_repo:
        forced_version_number_bump = True
    # create rta description file
    rta_descr_output_dir = os.path.join(SCRIPT_ROOT_DIR, pkg_constants.RTA_DESCRIPTION_FILE_DIR_NAME)
    bldinstallercommon.create_dirs(rta_descr_output_dir)
    architecture = bldinstallercommon.get_architecture()
    plat_suffix = bldinstallercommon.get_platform_suffix()
    rta_description_file_name = os.path.join( rta_descr_output_dir, pkg_constants.RTA_DESCRIPTION_FILE_NAME_BASE + '-' + plat_suffix + '-' + architecture + '-repo.txt')

    # handle repo build jobs
    for job in repo_job_list:
        create_online_repository(job, packages_base_url, forced_version_number_bump)
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
        staging_repo_updated, prod_pending_repo_updated = update_online_repo(job, update_staging_repo, update_production_repo)
        # write the rta description file only if staging repository creation was ok
        if (staging_repo_updated):
            rta_description_file = open(rta_description_file_name, 'a')
            rta_description_file.write(job.repo_url_specifier + ' ' + job.rta_key_list + '\n')
            rta_description_file.close()


# helper function to create online repository
def create_online_repository(build_job, packages_base_url, forced_version_number_bump):
    # ensure the string ends with '/'
    if not packages_base_url.endswith('/'):
        packages_base_url += '/'
    build_job.print_data()
    cmd_args = ['python', '-u', 'create_installer.py', \
                '-c', build_job.configurations_dir, \
                '-f', build_job.configurations_file, \
                '--create-repo', \
                '-l', build_job.license, \
                '--version-number=' + build_job.version_number, \
                '-u', urlparse.urljoin(packages_base_url, build_job.license), \
                '--ifw-tools='+ build_job.ifw_tools]
    if forced_version_number_bump:
        cmd_args += ['--force-version-number-increase']
    if (len(build_job.substitution_arg_list) > 0):
        for item in build_job.substitution_arg_list:
            cmd_args = cmd_args + [item]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)


# push online repository into remote server
def push_online_repository(server_addr, username, directory_to_copy, where_to_copy):
    print('Preparing to copy: {0}'.format(directory_to_copy))
    where_to_copy = ensure_unix_paths(where_to_copy)
    destination  = username + '@' + server_addr + ':' + where_to_copy + '/'
    cmd_args = [REMOTE_COPY_COMMAND, '-r', '.', destination]
    bldinstallercommon.do_execute_sub_process(cmd_args, directory_to_copy, True)


# init online repository directory structure at remote server
def init_repositories(job_list):
    print('Initializing repositories ...')
    init_env()
    server_addr = REPO_STAGING_SERVER_UNAME + '@' + REPO_STAGING_SERVER
    for item in job_list:
        # create test area paths
        test_area_path = generate_repo_path_for_test_area(item)
        create_remote_dirs(server_addr, test_area_path)
        # pending (merge) area paths
        pending_area_base_path_repo, pending_area_base_path_pkg = generate_repo_dest_path_pending(item)
        # delete old pending material first from pending area
        content_to_be_deleted = generate_repo_path_for_pending_area(item) + '/*'
        delete_online_repo_paths(server_addr, content_to_be_deleted)
        # create clean dir structure in pending area
        create_remote_dirs(server_addr, pending_area_base_path_pkg)
        create_remote_dirs(server_addr, pending_area_base_path_repo)


# generate the common part for the repo path
def generate_repo_path(build_job):
    path = REPOSITORY_BASE_NAME + '/' + build_job.repo_url_specifier
    return ensure_unix_paths(path)


# generate full path for test area repository
def generate_repo_path_for_test_area(build_job):
    path = REPO_STAGING_SERVER_TEST_REPO + '/' + build_job.license + '/'
    path += generate_repo_path(build_job)
    return ensure_unix_paths(path)


# generate pending area (base) path
def generate_repo_path_for_pending_area(build_job):
    path = REPO_STAGING_SERVER_TEST_REPO_PENDING + '/' + build_job.license + '/'
    path += build_job.repo_content_type + '/'
    path += generate_repo_path(build_job)
    return ensure_unix_paths(path)


# generate temporary 'pkg' and 'online_repository' pending area paths for repo update work
def generate_repo_dest_path_pending(repo_job):
    base_path_pending = generate_repo_path_for_pending_area(repo_job)
    dest_path_repository = ensure_unix_paths(os.path.join(base_path_pending, 'online_repository'))
    dest_path_pkg = ensure_unix_paths(os.path.join(base_path_pending, 'pkg'))
    return dest_path_repository, dest_path_pkg


# helper function to create remote directories
def create_remote_dirs(server, dir_path):
    temp_path = ensure_unix_paths(dir_path)
    cmd_args = [SSH_COMMAND, '-t', '-t', server, 'mkdir -p', temp_path]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)


# helper function to delete online repository directories on remote server
def delete_online_repo_paths(server_addr, path_to_be_deleted):
    temp_path = ensure_unix_paths(path_to_be_deleted)
    cmd_args = [SSH_COMMAND, '-t', '-t', server_addr, 'rm -rf', temp_path]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)


# ensure unix style paths
def ensure_unix_paths(path):
    temp_path = path.replace('\\', '/')
    temp_path = temp_path.replace('//', '/')
    return temp_path


# helper function to generate correct path structure for pending area
def generate_repo_pending_base_path(build_job):
    base_path_pending = REPO_STAGING_SERVER_TEST_REPO_PENDING + '/' + build_job.license + '/'
    base_path_pending += build_job.repo_content_type + '/' + REPOSITORY_BASE_NAME + '/' + build_job.repo_url_specifier
    return base_path_pending


# execute online repository update
def update_online_repo(job, update_staging_repo, update_production_repo):
    staging_server_addr = REPO_STAGING_SERVER_UNAME + '@' + REPO_STAGING_SERVER
    staging_server_ifw_tools = 'installer-framework-build-linux-x64.7z'
    script = REPO_STAGING_SERVER_HOME_TOOLS + '/' + 'update_repository.py'
    repogen_tools = REPO_STAGING_SERVER_HOME + '/' + staging_server_ifw_tools
    # determine paths on test server
    staging_source_repo, staging_source_pkg = generate_repo_dest_path_pending(job)
    repo_components_to_update = job.repo_components_to_update
    staging_repo_updated = False
    production_pending_repo_updated = False

    # do we update the staging repository
    if update_staging_repo:
        # determine target repo
        staging_target_repo = REPO_STAGING_SERVER_TEST_REPO + '/' + job.license + '/' + REPOSITORY_BASE_NAME + '/' + job.repo_url_specifier
        cmd_args = [SSH_COMMAND, '-t', '-t', staging_server_addr]
        cmd_args = cmd_args + ['python', script]
        cmd_args = cmd_args + ['--repogen_tools=' + repogen_tools]
        cmd_args = cmd_args + ['--source_pkg=' + staging_source_pkg]
        cmd_args = cmd_args + ['--source_repo=' + staging_source_repo]
        cmd_args = cmd_args + ['--target_repo=' + staging_target_repo]
        cmd_args = cmd_args + ['--components_to_update=' + repo_components_to_update]
        bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)
        staging_repo_updated = True

    # do we also update the production repository?
    if update_production_repo:
        # (1) pull repo from production into staging server 'temp' location
        production_repo = PROD_USER + '@' + PROD_ADDR
        production_repo_path = PROD_SRV_REPO_BASE_PATH + '/' + REPOSITORY_BASE_NAME + '/' + job.repo_url_specifier
        production_repo_path = ensure_unix_paths(production_repo_path)
        prod_url = production_repo + ":" + production_repo_path
        staging_prod_repo_temp_path = REPO_STAGING_SERVER_TEST_REPO_DIST_WORK + '/' + job.license + '/' + REPOSITORY_BASE_NAME + '/' + job.repo_url_specifier
        # delete old existing 'temp' paths
        delete_online_repo_paths(staging_server_addr, staging_prod_repo_temp_path)
        # create 'temp' location where to pull the repo from production
        create_remote_dirs(staging_server_addr, staging_prod_repo_temp_path)
        # chop out the last path component for remote copy as it would result in duplicate nested subdirectory
        remote_copy_path = staging_prod_repo_temp_path
        if (remote_copy_path.endswith('/')):
            remote_copy_path = remote_copy_path[:len(remote_copy_path) - 1]
        remote_copy_path = os.path.dirname(remote_copy_path)
        remote_copy_path = ensure_unix_paths(remote_copy_path)
        # test if production repository exists
        cmd_args = [SSH_COMMAND, '-t', '-t', staging_server_addr, 'ssh', '-t', '-t', production_repo, 'test', '-d', production_repo_path]
        return_code, output = bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, False)
        if return_code == -1:
            print('Pulling production repository: {0}'.format(prod_url))
            cmd_args = [SSH_COMMAND, '-t', '-t', staging_server_addr, 'rsync', '-rk', prod_url, remote_copy_path]
            bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)
        # (2) update
        cmd_args = [SSH_COMMAND, '-t', '-t', staging_server_addr]
        cmd_args = cmd_args + ['python', script]
        cmd_args = cmd_args + ['--repogen_tools=' + repogen_tools]
        cmd_args = cmd_args + ['--source_pkg=' + staging_source_pkg]
        cmd_args = cmd_args + ['--source_repo=' + staging_source_repo]
        cmd_args = cmd_args + ['--target_repo=' + staging_prod_repo_temp_path]
        cmd_args = cmd_args + ['--components_to_update=' + repo_components_to_update]
        cmd_args = cmd_args + ['--update_new_components_only'] # for production repos we update only those with version number increase
        bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)
        # (3) push updated repo back to production
        prod_server_pending_area_dir = PROD_SRV_REPO_PENDING_AREA_DIR + '/' + REPOSITORY_BASE_NAME + '/' + job.repo_url_specifier
        prod_server_pending_area_dir = ensure_unix_paths(prod_server_pending_area_dir)
        cmd_args_log_to_staging = [SSH_COMMAND, '-t', '-t', staging_server_addr]
        cmd_args_log_to_prod = cmd_args_log_to_staging + ['ssh', '-t', '-t', PROD_USER + '@' + PROD_ADDR ]
        # delete old stuff from pending area, but do sanity check first!
        if (os.path.normpath(PROD_SRV_REPO_PENDING_AREA_DIR) in (os.path.normpath(PROD_SRV_REPO_BASE_PATH + '/' + REPOSITORY_BASE_NAME))):
            print('*** Fatal error!!! You are trying to delete production repository: '.format(prod_server_pending_area_dir))
            print('*** Aborting ...')
            sys.exit(-1)
        cmd_args_rm_old = cmd_args_log_to_prod + ['rm', '-rf', prod_server_pending_area_dir]
        bldinstallercommon.do_execute_sub_process(cmd_args_rm_old, SCRIPT_ROOT_DIR, True)
        # create pending dirs into production server
        cmd_args_mkdirp = cmd_args_log_to_prod + ['mkdir', '-p', prod_server_pending_area_dir]
        bldinstallercommon.do_execute_sub_process(cmd_args_mkdirp, SCRIPT_ROOT_DIR, True)
        # chop out the last path component for remote copy as it would result in duplicate nested subdirectory
        prod_dest_path = production_repo + ':' + PROD_SRV_REPO_PENDING_AREA_DIR + '/' + REPOSITORY_BASE_NAME + '/' + job.repo_url_specifier
        if (prod_dest_path.endswith('/')):
            prod_dest_path = prod_dest_path[:len(prod_dest_path) - 1]
        prod_dest_path = os.path.dirname(prod_dest_path)
        # copy updated repo into 'waiting' area on production server
        print('Pushing [{0}] into [{1}]'.format(staging_prod_repo_temp_path, prod_dest_path))
        cmd_args = cmd_args_log_to_staging + ['rsync', '-r', staging_prod_repo_temp_path, prod_dest_path]
        bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)
        print('Repository [{0}] updated and pushed into production server pending area successfully.'.format(job.repo_url_specifier))
        production_pending_repo_updated = True

    return staging_repo_updated, production_pending_repo_updated


# init environment
def init_env():
    global REPO_STAGING_SERVER
    global REPO_STAGING_SERVER_UNAME
    global PKG_SERVER_URL
    global REPO_STAGING_SERVER_HOME
    global REPO_STAGING_SERVER_HOME_TOOLS
    global SSH_COMMAND
    global REMOTE_COPY_COMMAND
    global IFW_TOOLS_BASE_URL
    global CONFIGURATIONS_FILE_BASE_DIR
    global PROD_USER
    global PROD_ADDR
    global PROD_SRV_REPO_BASE_PATH
    global PROD_SRV_REPO_PENDING_AREA_DIR
    global INIT_DONE
    if INIT_DONE:
        return

    REPO_STAGING_SERVER             = os.environ['PKG_STAGING_SERVER']
    REPO_STAGING_SERVER_UNAME       = os.environ['PKG_STAGING_SERVER_UNAME']
    PKG_SERVER_URL                  = os.environ['PKG_SERVER_URL']
    REPO_STAGING_SERVER_HOME        = os.environ['REPO_STAGING_SERVER_HOME']
    REPO_STAGING_SERVER_HOME_TOOLS  = REPO_STAGING_SERVER_HOME + '/' + REPO_STAGING_SERVER_HOME_TOOLS
    IFW_TOOLS_BASE_URL              = os.environ['IFW_TOOLS_BASE_URL']
    CONFIGURATIONS_FILE_BASE_DIR    = os.environ['CONFIGURATIONS_FILE_BASE_DIR']
    PROD_USER                       = os.environ['PROD_USER']
    PROD_ADDR                       = os.environ['PROD_ADDR']
    PROD_SRV_REPO_BASE_PATH         = os.environ['PROD_SRV_REPO_BASE_PATH']
    PROD_SRV_REPO_PENDING_AREA_DIR  = os.environ['PROD_SRV_REPO_PENDING_AREA_DIR']
    print('Staging server: {0}'.format(REPO_STAGING_SERVER))
    print('Staging server uname: {0}'.format(REPO_STAGING_SERVER_UNAME))
    print('Staging server home: {0}'.format(REPO_STAGING_SERVER_HOME))
    print('Staging server tools dir: {0}'.format(REPO_STAGING_SERVER_HOME_TOOLS))
    print('Production server: {0}'.format(PROD_ADDR))
    print('Production server uname: {0}'.format(PROD_USER))
    print('Production server repository base path: {0}'.format(PROD_SRV_REPO_BASE_PATH))
    print('Production server pending area: {0}'.format(PROD_SRV_REPO_PENDING_AREA_DIR))
    print('Packages server base URL: {0}'.format(PKG_SERVER_URL))
    print('IFW tools base url: {0}'.format(IFW_TOOLS_BASE_URL))
    print('Configurations file base dir: {0}'.format(CONFIGURATIONS_FILE_BASE_DIR))
    bldinstallercommon.init_common_module(SCRIPT_ROOT_DIR)
    if bldinstallercommon.is_win_platform():
        SSH_COMMAND = '%SSH%'
        REMOTE_COPY_COMMAND = '%SCP%'
    INIT_DONE = True

