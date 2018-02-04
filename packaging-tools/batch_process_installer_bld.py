#!/usr/bin/env python
#############################################################################
##
## Copyright (C) 2016 The Qt Company Ltd.
## Contact: https://www.qt.io/licensing/
##
## This file is part of the release tools of the Qt Toolkit.
##
## $QT_BEGIN_LICENSE:GPL-EXCEPT$
## Commercial License Usage
## Licensees holding valid commercial Qt licenses may use this file in
## accordance with the commercial license agreement provided with the
## Software or, alternatively, in accordance with the terms contained in
## a written agreement between you and The Qt Company. For licensing terms
## and conditions see https://www.qt.io/terms-conditions. For further
## information use the contact form at https://www.qt.io/contact-us.
##
## GNU General Public License Usage
## Alternatively, this file may be used under the terms of the GNU
## General Public License version 3 as published by the Free Software
## Foundation with exceptions as appearing in the file LICENSE.GPL3-EXCEPT
## included in the packaging of this file. Please review the following
## information to ensure the GNU General Public License requirements will
## be met: https://www.gnu.org/licenses/gpl-3.0.html.
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

SCRIPT_ROOT_DIR                         = os.path.dirname(os.path.realpath(__file__))

# search/replace tags in configuration files
GLOBAL_VERSION                          = '%GLOBAL_VERSION%'
GLOBAL_VERSION_AND_TAG                  = '%GLOBAL_VERSION_AND_TAG%'


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
        self.installer_name             = installer_name
        self.rta_key_list               = rta_keys.replace(' ', '')
        self.format_substitution_list(substitution_list)

    # format substitution list so that it can be used by create_installer.py
    def format_substitution_list(self, substitution_list):
        item_list = substitution_list.split(',')
        for item in item_list:
            temp = item.replace(' ', '')
            if temp:
                if bldinstallercommon.is_win_platform():
                    # On Windows we must escape the '%' so that the subprocess shell will
                    # not attempt to replace the environment variables
                    temp = temp.replace('%', '^%')
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
            raise RuntimeError('*** Fatal error! <node_name> not defined for build job?')
        if not self.license:
            raise RuntimeError('*** Fatal error! <license> not defined for: %s' % self.node_name)
        if not self.configurations_dir:
            raise IOError('*** Fatal error! <configurations_dir> not defined for: %s' % self.node_name)
        if not self.configurations_file:
            raise IOError('*** Fatal error! <configurations_file> not defined for: %s' % self.node_name)
        if not self.ifw_tools:
            raise RuntimeError('*** Fatal error! <ifw_tools> not defined for: %s' % self.node_name)
        if self.is_repo_job:
            if not self.repo_content_type:
                raise RuntimeError('*** Fatal error! <repo_content_type> not defined for: %s' % self.node_name)
            if not self.repo_components_to_update:
                raise RuntimeError('*** Fatal error! <repo_components_to_update> not defined for: %s' % self.node_name)
            if not self.repo_url_specifier:
                raise RuntimeError('*** Fatal error! <repo_url_specifier> not defined for: %s' % self.node_name)
        # all ok
        return True

    def get_package_type(self):
        items = self.node_name.split('.')
        if len(items) >= 6:
            return items[5]


def preformat_global_version_and_tag(arg_substitution_list, global_version, global_version_tag):
    version = global_version
    if global_version_tag:
        version = version + '-' + global_version_tag
    temp = arg_substitution_list.replace(GLOBAL_VERSION_AND_TAG, version).replace(GLOBAL_VERSION, global_version)
    return temp


def is_valid_job_type(job_type_specifier):
    if (job_type_specifier == 'repository'):
        return True
    if (job_type_specifier == 'offline'):
        return True
    if (job_type_specifier == 'online'):
        return True
    return False


# parse online repository build jobs for given platform and architecture
#<branch>.<qt_version>.<offline/repository>.<host_os>.<architecture>.<package_type>
def get_repo_job_list(optionDict, branch, arch, global_version, global_version_tag):
    return get_job_list(optionDict, 'repository', branch, arch, global_version, global_version_tag)


# parse build jobs for given platform and architecture
#<branch>.<qt_version>.<offline/repository>.<host_os>.<architecture>.<package_type>
def get_job_list(optionDict, job_type_specifier, branch, arch, global_version, global_version_tag):
    conf_file           = optionDict['RELEASE_DESCRIPTION_FILE']
    license_type        = optionDict['LICENSE']
    platform            = optionDict['HOST_PLATFORM']
    conf_file_base_dir  = optionDict['CONFIGURATIONS_FILE_BASE_DIR']
    ifw_base_url        = optionDict['IFW_TOOLS_BASE_URL']
    print('Get [{0}] build job list for: {1}'.format(job_type_specifier, platform + '-' + arch))
    if not os.path.isfile(conf_file):
        raise IOError('*** Fatal error! Given file does not exist: %s' % conf_file)
    # ensure the string ends with '/'
    if not ifw_base_url.endswith('/'):
        ifw_base_url += '/'
    parser = ConfigParser.ConfigParser()
    parser.readfp(open(conf_file))
    # validate job type
    if not is_valid_job_type(job_type_specifier):
        raise RuntimeError('*** Fatal error! Unsupported job type specifier given: %s' % job_type_specifier)
    # determine which ifw tools to use (which platform)
    ifw_tools = bldinstallercommon.safe_config_key_fetch(parser, 'ifwtools', platform + '-' + arch)
    if not ifw_tools:
        raise RuntimeError('*** Fatal error! Unable to find ifw tools for_ %s' % (platform + '-' + arch))
    ifw_tools_url = urlparse.urljoin(ifw_base_url, ifw_tools)
    # check if repository build job
    is_repo_job = False
    if job_type_specifier == 'repository':
        is_repo_job = True
    # first read global arg substitution list applicable for all build jobs in this file
    global_arg_substitution_list = bldinstallercommon.safe_config_key_fetch(parser, 'release.global', 'arg_substitution_list')
    # parse
    job_list = []
    for s in parser.sections():
        section_parts = s.split('.')
        if (len(section_parts) < 5):
            continue
        if (section_parts[0] == branch and section_parts[2] == job_type_specifier):
            # Check first if this job was assigned to dedicated machine label
            machine_label = bldinstallercommon.safe_config_key_fetch(parser, s, 'assign_to_machine_label')
            if machine_label:
                if not machine_label == optionDict['TARGET_ENV']:
                    continue
            else: # If not then check against the platform and arch
                if not ((section_parts[3] == platform) and (section_parts[4] == arch)):
                    continue

            # parse from conf file
            version_number = bldinstallercommon.safe_config_key_fetch(parser, s, 'version_number')
            if not version_number:
                version_number = global_version
            version_number_tag = bldinstallercommon.safe_config_key_fetch(parser, s, 'version_number_tag')
            if not version_number_tag:
                version_number_tag = global_version_tag
            arg_configurations_file = bldinstallercommon.safe_config_key_fetch(parser, s, 'arg_configurations_file')
            if not arg_configurations_file:
                raise RuntimeError('*** Fatal error! Configuration file not defined for: %s' % s)

            # for triggering rta later on if specified
            rta_key_list = bldinstallercommon.safe_config_key_fetch(parser, s, 'rta_key_list')
            # preferred installer name
            installer_name = bldinstallercommon.safe_config_key_fetch(parser, s, 'installer_name')
            arg_substitution_list = bldinstallercommon.safe_config_key_fetch(parser, s, 'arg_substitution_list')
            arg_substitution_list += ',' + global_arg_substitution_list
            arg_substitution_list += ',' + "%BUILD_NUMBER%=" + optionDict['BUILD_NUMBER']
            arg_substitution_list = arg_substitution_list.replace('\n', '')
            arg_substitution_list = preformat_global_version_and_tag(arg_substitution_list, global_version, global_version_tag)
            repo_content_type           = ''
            repo_components_to_update   = ''
            repo_url_specifier          = ''
            # if online repo job
            if job_type_specifier == 'repository':
                repo_content_type = bldinstallercommon.safe_config_key_fetch(parser, s, 'repo_content_type')
                if not repo_content_type:
                    repo_content_type = arg_configurations_file.split("/")[-1]  # if the 'repo_content_type' (for temp dir name) is not defined then parse it from the conf file
                repo_components_to_update = bldinstallercommon.safe_config_key_fetch(parser, s, 'repo_components_to_update')
                if not repo_components_to_update:
                    raise RuntimeError('*** Fatal error! <repo_components_to_update> not defined for: %s' % s)
                repo_url_specifier = bldinstallercommon.safe_config_key_fetch(parser, s, 'repo_url_specifier')
                if not repo_url_specifier:
                    raise RuntimeError('*** Fatal error! <repo_url_specifier> not defined for: %s' % s)
            # determine full path for the conf file
            full_conf_file_path = os.path.join(conf_file_base_dir, arg_configurations_file)
            # create build job
            job = BuildJob(is_repo_job, license_type, s, arch, version_number, version_number_tag, conf_file_base_dir, full_conf_file_path, ifw_tools_url, arg_substitution_list, repo_content_type, repo_components_to_update, repo_url_specifier, installer_name, rta_key_list)
            if (job.validate()):
                job_list.append(job)
    return job_list


# execute
# - online installer build(s)
def handle_installer_build(optionDict, installer_type, branch, arch):
    conf_file = optionDict['RELEASE_DESCRIPTION_FILE']
    print('Parsing [{0}] installer build jobs from: {0}'.format(conf_file))
    if not os.path.isfile(conf_file):
        raise IOError('*** Fatal error! Given file does not exist: {0}'.format(conf_file))
    init_env(optionDict)
    license_type      = optionDict['LICENSE']
    platform          = optionDict['HOST_PLATFORM']
    packages_base_url = optionDict['PACKAGE_STORAGE_SERVER_PATH_HTTP']
    # parse conf file
    parser = ConfigParser.ConfigParser()
    parser.readfp(open(conf_file))
    section_name        = branch + '.' + 'global'
    global_version      = bldinstallercommon.safe_config_key_fetch(parser, section_name, 'version')
    global_version_tag  = bldinstallercommon.safe_config_key_fetch(parser, section_name, 'version_tag')
    if not global_version:
        raise RuntimeError('*** Fatal error! Invalid values in {0} -> {1}'.format(conf_file, section_name))
    # parse build jobs
    job_list = get_job_list(optionDict, installer_type, branch, arch, global_version, global_version_tag)
    if (len(job_list) == 0):
        raise RuntimeError('*** Fatal error! No [{0}] installer build jobs found from: {1}. Probably an error?'.format(installer_type, conf_file))
    installer_output_dir = os.path.join(SCRIPT_ROOT_DIR, pkg_constants.INSTALLER_OUTPUT_DIR_NAME)
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
        raise RuntimeError('*** Fatal error! No installers generated into: %s' % installer_output_dir)


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
    cmd_args = cmd_args + ['-u', packages_base_url]
    cmd_args = cmd_args + ['--ifw-tools=' + job.ifw_tools]
    cmd_args = cmd_args + ['--preferred-installer-name=' + job.installer_name]
    if (len(job.substitution_arg_list) > 0):
        for item in job.substitution_arg_list:
            cmd_args = cmd_args + [item]
    # execute, do not bail out if installer job fails
    subprocess_exec_stataus = False
    try:
        bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR)
        subprocess_exec_stataus = True
    except:
        # catch any interrupt into installer creation, we assume the operation failed
        subprocess_exec_stataus = False
    return subprocess_exec_stataus

# execute:
# - online reposiory build
# - upload repository into test server
# - update existing repository at test server with new content
def handle_repo_build(optionDict, branch, arch, update_staging_repo, update_production_repo):
    conf_file = optionDict['RELEASE_DESCRIPTION_FILE']
    if not os.path.isfile(conf_file):
        raise IOError('*** Fatal error! Given file does not exist: %s' % conf_file)
    init_env(optionDict)
    packages_base_url   = optionDict['PACKAGE_STORAGE_SERVER_PATH_HTTP']
    ifw_base_url        = optionDict['IFW_TOOLS_BASE_URL']
    release_tools_dir   = SCRIPT_ROOT_DIR
    # parse conf file
    parser = ConfigParser.ConfigParser()
    parser.readfp(open(conf_file))
    section_name = branch + '.' + 'global'
    global_version     = bldinstallercommon.safe_config_key_fetch(parser, section_name, 'version')
    global_version_tag = bldinstallercommon.safe_config_key_fetch(parser, section_name, 'version_tag')
    # parse build jobs
    repo_job_list = get_repo_job_list(optionDict, branch, arch, global_version, global_version_tag)
    if (len(repo_job_list) == 0):
        raise RuntimeError('*** Fatal error! No repository build jobs found. Probably an error? %s' % conf_file)
    # init repo dirs
    init_repositories(optionDict, repo_job_list)
    # is this snapshot build? Then enable component version number forced update
    forced_version_number_bump = False
    if update_staging_repo and not update_production_repo:
        forced_version_number_bump = True
    if optionDict.get('FORCE_VERSION_NUMBER_INCREASE') in ['yes', 'true', '1']:
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
        dest_path_repository, dest_path_pkg = generate_repo_dest_path_pending(optionDict, job)
        # copy repo content to test server
        source_path_repository  = os.path.join(release_tools_dir, 'repository')
        source_path_pkg         = os.path.join(release_tools_dir, 'pkg')
        push_online_repository(optionDict, optionDict['PKG_STAGING_SERVER'], optionDict['PKG_STAGING_SERVER_UNAME'], source_path_repository, dest_path_repository)
        push_online_repository(optionDict, optionDict['PKG_STAGING_SERVER'], optionDict['PKG_STAGING_SERVER_UNAME'], source_path_pkg, dest_path_pkg)
        # remove local repository and pkg directories
        bldinstallercommon.remove_tree(source_path_repository)
        bldinstallercommon.remove_tree(source_path_pkg)
        # update repo in testing area
        staging_repo_updated, production_repo_updated = update_online_repo(optionDict, job, update_staging_repo, update_production_repo)
        # write the rta description file only if staging repository creation was ok
        # remove also temp staging repositories from 'staging_pending' and 'production_dist_update_work' directories
        server_addr = optionDict['PKG_STAGING_SERVER_UNAME'] + '@' + optionDict['PKG_STAGING_SERVER']
        if (staging_repo_updated):
            rta_description_file = open(rta_description_file_name, 'a')
            rta_description_file.write(job.repo_url_specifier + ' ' + job.rta_key_list + '\n')
            rta_description_file.close()
            staging_temp_content_to_be_deleted = generate_repo_path_for_pending_area(optionDict, job)
            delete_online_repo_paths(optionDict, server_addr, staging_temp_content_to_be_deleted)
        if (production_repo_updated):
            production_temp_content_to_be_deleted = optionDict['REPO_STAGING_SERVER_TEST_REPO_DIST_WORK'] + '/' + optionDict['ONLINE_REPOSITORY_BASE_NAME'] + '/' + job.repo_url_specifier
            delete_online_repo_paths(optionDict, server_addr, production_temp_content_to_be_deleted)


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
                '-u', packages_base_url, \
                '--ifw-tools='+ build_job.ifw_tools]
    if forced_version_number_bump:
        cmd_args += ['--force-version-number-increase']
    if (len(build_job.substitution_arg_list) > 0):
        for item in build_job.substitution_arg_list:
            cmd_args = cmd_args + [item]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR)


# push online repository into remote server
def push_online_repository(optionDict, server_addr, username, directory_to_copy, where_to_copy):
    print('Preparing to copy: {0}'.format(directory_to_copy))
    where_to_copy = ensure_unix_paths(where_to_copy)
    destination  = username + '@' + server_addr + ':' + where_to_copy + '/'
    cmd_args = [optionDict['SCP_COMMAND'], '-r', '.', destination]
    bldinstallercommon.do_execute_sub_process(cmd_args, directory_to_copy)


# init online repository directory structure at remote server
def init_repositories(optionDict, job_list):
    print('Initializing repositories ...')
    init_env(optionDict)
    server_addr = optionDict['PKG_STAGING_SERVER_UNAME'] + '@' + optionDict['PKG_STAGING_SERVER']
    for item in job_list:
        # create test area paths
        test_area_path = generate_repo_path_for_test_area(optionDict, item)
        create_remote_dirs(optionDict, server_addr, test_area_path)
        # pending (merge) area paths
        pending_area_base_path_repo, pending_area_base_path_pkg = generate_repo_dest_path_pending(optionDict, item)
        # delete old pending material first from pending area
        content_to_be_deleted = generate_repo_path_for_pending_area(optionDict, item) + '/*'
        delete_online_repo_paths(optionDict, server_addr, content_to_be_deleted)
        # create clean dir structure in pending area
        create_remote_dirs(optionDict, server_addr, pending_area_base_path_pkg)
        create_remote_dirs(optionDict, server_addr, pending_area_base_path_repo)


# generate the common part for the repo path
def generate_repo_path(optionDict, build_job):
    path = optionDict['ONLINE_REPOSITORY_BASE_NAME'] + '/' + build_job.repo_url_specifier
    return ensure_unix_paths(path)


# generate full path for test area repository
def generate_repo_path_for_test_area(optionDict, build_job):
    path = optionDict['REPO_STAGING_SERVER_TEST_REPO'] + '/'
    path += generate_repo_path(optionDict, build_job)
    return ensure_unix_paths(path)


# generate pending area (base) path
def generate_repo_path_for_pending_area(optionDict, build_job):
    path = optionDict['REPO_STAGING_SERVER_TEST_REPO_PENDING'] + '/'
    path += build_job.repo_content_type + '/'
    path += generate_repo_path(optionDict, build_job)
    return ensure_unix_paths(path)


# generate temporary 'pkg' and 'online_repository' pending area paths for repo update work
def generate_repo_dest_path_pending(optionDict, repo_job):
    base_path_pending = generate_repo_path_for_pending_area(optionDict, repo_job)
    dest_path_repository = ensure_unix_paths(os.path.join(base_path_pending, 'online_repository'))
    dest_path_pkg = ensure_unix_paths(os.path.join(base_path_pending, 'pkg'))
    return dest_path_repository, dest_path_pkg


# helper function to create remote directories
def create_remote_dirs(optionDict, server, dir_path):
    temp_path = ensure_unix_paths(dir_path)
    cmd_args = [optionDict['SSH_COMMAND'], '-t', '-t', server, 'mkdir -p', temp_path]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR)


# helper function to delete online repository directories on remote server
def delete_online_repo_paths(optionDict, server_addr, path_to_be_deleted):
    temp_path = ensure_unix_paths(path_to_be_deleted)
    cmd_args = [optionDict['SSH_COMMAND'], '-t', '-t', server_addr, 'rm -rf', temp_path]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR)


# ensure unix style paths
def ensure_unix_paths(path):
    temp_path = path.replace('\\', '/')
    temp_path = temp_path.replace('//', '/')
    return temp_path


# execute online repository update
def update_online_repo(optionDict, job, update_staging_repo, update_production_repo):
    staging_server_addr = optionDict['PKG_STAGING_SERVER_UNAME'] + '@' + optionDict['PKG_STAGING_SERVER']
    staging_server_ifw_tools = 'installer-framework-build-linux-x64.7z'
    script = optionDict['REPO_STAGING_SERVER_HOME_TOOLS'] + '/' + 'update_repository.py'
    repogen_tools = optionDict['IFW_TOOLS_BASE_URL'] + '/' + staging_server_ifw_tools
    # determine paths on test server
    staging_source_repo, staging_source_pkg = generate_repo_dest_path_pending(optionDict, job)
    repo_components_to_update = job.repo_components_to_update
    staging_repo_updated = False
    production_pending_repo_updated = False

    # do we update the staging repository
    if update_staging_repo:
        # determine target repo
        staging_target_repo = optionDict['REPO_STAGING_SERVER_TEST_REPO'] + '/' + optionDict['ONLINE_REPOSITORY_BASE_NAME'] + '/' + job.repo_url_specifier
        cmd_args = [optionDict['SSH_COMMAND'], '-t', '-t', staging_server_addr]
        cmd_args = cmd_args + ['python', script]
        cmd_args = cmd_args + ['--repogen_tools=' + repogen_tools]
        cmd_args = cmd_args + ['--source_pkg=' + staging_source_pkg]
        cmd_args = cmd_args + ['--source_repo=' + staging_source_repo]
        cmd_args = cmd_args + ['--target_repo=' + staging_target_repo]
        cmd_args = cmd_args + ['--components_to_update=' + repo_components_to_update]
        bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR)
        staging_repo_updated = True

    # do we also update the production repository?
    if update_production_repo:
        # (1) pull repo from production into staging server 'temp' location
        production_repo = optionDict['PROD_USER'] + '@' + optionDict['PROD_ADDR']
        production_repo_path = optionDict['PROD_SRV_REPO_BASE_PATH'] + '/' + optionDict['ONLINE_REPOSITORY_BASE_NAME'] + '/' + job.repo_url_specifier
        production_repo_path = ensure_unix_paths(production_repo_path)
        prod_url = production_repo + ":" + production_repo_path
        staging_prod_repo_temp_path = optionDict['REPO_STAGING_SERVER_TEST_REPO_DIST_WORK'] + '/' + optionDict['ONLINE_REPOSITORY_BASE_NAME'] + '/' + job.repo_url_specifier
        # delete old existing 'temp' paths
        delete_online_repo_paths(optionDict, staging_server_addr, staging_prod_repo_temp_path)
        # create 'temp' location where to pull the repo from production
        create_remote_dirs(optionDict, staging_server_addr, staging_prod_repo_temp_path)
        # chop out the last path component for remote copy as it would result in duplicate nested subdirectory
        remote_copy_path = staging_prod_repo_temp_path
        if (remote_copy_path.endswith('/')):
            remote_copy_path = remote_copy_path[:len(remote_copy_path) - 1]
        remote_copy_path = os.path.dirname(remote_copy_path)
        remote_copy_path = ensure_unix_paths(remote_copy_path)
        # test if production repository exists
        cmd_args = [optionDict['SSH_COMMAND'], '-t', '-t', staging_server_addr, 'ssh', '-t', '-t', production_repo, 'test', '-d', production_repo_path]
        return_code, dummy = bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, abort_on_fail=False)
        if return_code == -1:
            print('Pulling production repository: [{0}] into [{1}]'.format(prod_url, remote_copy_path))
            cmd_args = [optionDict['SSH_COMMAND'], '-t', '-t', staging_server_addr, 'rsync', '-rk', prod_url, remote_copy_path]
            bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR)
        # (2) update
        cmd_args = [optionDict['SSH_COMMAND'], '-t', '-t', staging_server_addr]
        cmd_args = cmd_args + ['python', script]
        cmd_args = cmd_args + ['--repogen_tools=' + repogen_tools]
        cmd_args = cmd_args + ['--source_pkg=' + staging_source_pkg]
        cmd_args = cmd_args + ['--source_repo=' + staging_source_repo]
        cmd_args = cmd_args + ['--target_repo=' + staging_prod_repo_temp_path]
        cmd_args = cmd_args + ['--components_to_update=' + repo_components_to_update]
        cmd_args = cmd_args + ['--update_new_components_only'] # for production repos we update only those with version number increase
        bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR)
        # (3) push updated repo back to production
        prod_server_pending_area_dir = optionDict['PROD_SRV_REPO_PENDING_AREA_DIR'] + '/' + optionDict['ONLINE_REPOSITORY_BASE_NAME'] + '/' + job.repo_url_specifier
        prod_server_pending_area_dir = ensure_unix_paths(prod_server_pending_area_dir)
        cmd_args_log_to_staging = [optionDict['SSH_COMMAND'], '-t', '-t', staging_server_addr]
        cmd_args_log_to_prod = cmd_args_log_to_staging + ['ssh', '-t', '-t', optionDict['PROD_USER'] + '@' + optionDict['PROD_ADDR'] ]
        # delete old stuff from pending area, but do sanity check first!
        if (os.path.normpath(optionDict['PROD_SRV_REPO_PENDING_AREA_DIR']) in (os.path.normpath(optionDict['PROD_SRV_REPO_BASE_PATH'] + '/' + optionDict['ONLINE_REPOSITORY_BASE_NAME']))):
            raise RuntimeError('*** Fatal error!!! You are trying to delete production repository: %s' % prod_server_pending_area_dir)
        cmd_args_rm_old = cmd_args_log_to_prod + ['rm', '-rf', prod_server_pending_area_dir]
        bldinstallercommon.do_execute_sub_process(cmd_args_rm_old, SCRIPT_ROOT_DIR)
        # create pending dirs into production server
        cmd_args_mkdirp = cmd_args_log_to_prod + ['mkdir', '-p', prod_server_pending_area_dir]
        bldinstallercommon.do_execute_sub_process(cmd_args_mkdirp, SCRIPT_ROOT_DIR)
        # chop out the last path component for remote copy as it would result in duplicate nested subdirectory
        prod_dest_path = production_repo + ':' + optionDict['PROD_SRV_REPO_PENDING_AREA_DIR'] + '/' + optionDict['ONLINE_REPOSITORY_BASE_NAME'] + '/' + job.repo_url_specifier
        if (prod_dest_path.endswith('/')):
            prod_dest_path = prod_dest_path[:len(prod_dest_path) - 1]
        prod_dest_path = os.path.dirname(prod_dest_path)
        # copy updated repo into 'waiting' area on production server
        print('Pushing [{0}] into [{1}]'.format(staging_prod_repo_temp_path, prod_dest_path))
        cmd_args = cmd_args_log_to_staging + ['rsync', '-r', staging_prod_repo_temp_path, prod_dest_path]
        bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR)
        print('Repository [{0}] updated and pushed into production server pending area successfully.'.format(job.repo_url_specifier))
        production_pending_repo_updated = True

    return staging_repo_updated, production_pending_repo_updated


# init environment
def init_env(optionDict):
    # Define the base directory under which the rest of directories exist
    # Staging specific
    optionDict['REPO_STAGING_SERVER_TEST_REPO']           = optionDict['STAGING_SRV_ONLINE_REPO_BASE_PATH'] + '/' + optionDict['LICENSE'] + '/staging'
    optionDict['REPO_STAGING_SERVER_TEST_REPO_PENDING']   = optionDict['STAGING_SRV_ONLINE_REPO_BASE_PATH'] + '/' + optionDict['LICENSE'] + '/staging_pending'
    optionDict['REPO_STAGING_SERVER_HOME_TOOLS']          = optionDict['REPO_STAGING_SERVER_HOME'] + '/qtsdk/packaging-tools'
    # Production specific directories are set directly from environment

    onlineRepositoryBaseName = os.environ.get('ONLINE_REPOSITORY_BASE_NAME')
    optionDict['ONLINE_REPOSITORY_BASE_NAME'] = onlineRepositoryBaseName if onlineRepositoryBaseName else 'qtsdkrepository'

    print('Staging server: {0}'.format(optionDict['PKG_STAGING_SERVER']))
    print('Staging server uname: {0}'.format(optionDict['PKG_STAGING_SERVER_UNAME']))
    print('Staging server base directory: {0}'.format(optionDict['REPO_STAGING_SERVER_TEST_REPO']))
    print('Staging server base directory pending: {0}'.format(optionDict['REPO_STAGING_SERVER_TEST_REPO_PENDING']))
    print('Staging server tools dir: {0}'.format(optionDict['REPO_STAGING_SERVER_HOME_TOOLS']))
    print('Production server: {0}'.format(optionDict['PROD_ADDR']))
    print('Production server uname: {0}'.format(optionDict['PROD_USER']))
    print('Production server base directory: {0}'.format(optionDict['PROD_SRV_REPO_BASE_PATH']))
    print('Production server base directory pending: {0}'.format(optionDict['PROD_SRV_REPO_PENDING_AREA_DIR']))
    print('Production server base directory dist update work: {0}'.format(optionDict['REPO_STAGING_SERVER_TEST_REPO_DIST_WORK']))
    print('Configurations file base dir: {0}'.format(optionDict['CONFIGURATIONS_FILE_BASE_DIR']))
    bldinstallercommon.init_common_module(SCRIPT_ROOT_DIR)
