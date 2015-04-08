#!/usr/bin/env python
#############################################################################
##
## Copyright (C) 2014 Digia Plc and/or its subsidiary(-ies).
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

import os
import sys
import fnmatch
import hashlib
import ConfigParser
import argparse
from time import gmtime, strftime
import bldinstallercommon

DEFAULT_ONLINE_UPDATE_JOB_FILE_NAME = 'online_update_jobs.conf'
ONLINE_UPDATE_JOB_CONFIG            = ''
ONLINE_REPOSITORY_ROOT_NAME         = 'qtsdkrepository'
ONLINE_REPOSITORY_META_FILE_NAME    = 'Updates.xml'


###############################
# Define possible update states
###############################
class UpdateState:
    initial = 'initial'
    ongoing = 'ongoing'
    done    = 'done'

ONLINE_UPDATE_JOB_STATES    = [UpdateState.initial, UpdateState.ongoing, UpdateState.done]


###############################################
# Container for single update job attributes
###############################################
class UpdateJob:

    def __init__(self, update_job_section, updates_xml, repo_platform, repo_specifier, repo_update_state):
        self.update_job_section    = update_job_section
        self.source_updates_xml    = updates_xml
        self.source_repo_platform  = repo_platform
        self.source_repo_specifier = repo_specifier
        self.repo_update_state     = repo_update_state
        self.target_updates_xml    = ''
        self.temp_id               = 0
        self.flush                 = False

    def __eq__(self, other):
        if self.source_updates_xml == other.source_updates_xml:
            if is_fresh_update_package(os.path.dirname(self.source_updates_xml)):
                return False
            else:
                return True
        return False

    def __hash__(self):
        return hash(('source_updates_xml', self.source_updates_xml))

    def validate(self):
        if self.repo_update_state != UpdateState.done:
            if not os.path.isfile(self.source_updates_xml):
                sys.exit('Given section [{0}] contains invalid Updates.xml path: {1}'.format(self.update_job_section, self.source_updates_xml))
        if self.repo_update_state not in ONLINE_UPDATE_JOB_STATES:
            sys.exit('Given section [{0}] contains unsupported repo_update_state: {1}'.format(self.update_job_section, self.repo_update_state))
        if not ONLINE_REPOSITORY_ROOT_NAME in self.source_updates_xml:
            sys.exit('*** Given Updates.xml file ignored, does not contain repository name specifier ({0}): {1}'.format(ONLINE_REPOSITORY_ROOT_NAME, self.source_updates_xml))

    def print_data(self):
        print('')
        print('[{0}]'.format(self.update_job_section))
        print('source_updates_xml:       {0}'.format(self.source_updates_xml))
        print('source_repo_platform:     {0}'.format(self.source_repo_platform))
        print('source_repo_specifier:    {0}'.format(self.source_repo_specifier))
        print('target_updates_xml:       {0}'.format(self.target_updates_xml))
        print('repo_update_state:        {0}'.format(self.repo_update_state))
        print('flush status:             {0}'.format(self.flush))



###########################################################
# Read existing update jobs from given configuration file
###########################################################
def read_update_job_info(file_name):
    update_jobs = []
    if not os.path.isfile(file_name):
        print('*** Warning - Unable to read existing update jobs as given file does not exist: {0}'.format(file_name))
        return update_jobs
    print('')
    print('')
    print('Parsing: {0}'.format(file_name))
    parser = ConfigParser.ConfigParser()
    parser.readfp(open(file_name))
    # parse
    for section in parser.sections():
        if section.startswith('UpdateJob.'):
            updates_xml       = bldinstallercommon.safe_config_key_fetch(parser, section, 'updates_xml')
            repo_platform     = bldinstallercommon.safe_config_key_fetch(parser, section, 'repo_platform')
            repo_specifier    = bldinstallercommon.safe_config_key_fetch(parser, section, 'repo_specifier')
            repo_update_state = bldinstallercommon.safe_config_key_fetch(parser, section, 'repo_update_state')
            update_job = UpdateJob(section, updates_xml, repo_platform, repo_specifier, repo_update_state)
            update_jobs.append(update_job)
    # validate
    for item in update_jobs:
        item.validate()
    return update_jobs


###########################################
# Store update jobs into configuration file
###########################################
def store_update_job_info(file_name, update_jobs):
    print('Writing to: {0}'.format(file_name))
    cfgfile = open(file_name,'w')
    for update_job in update_jobs:
        section_name = update_job.update_job_section
        config = ConfigParser.ConfigParser()
        config.add_section(section_name)
        config.set(section_name, 'updates_xml', update_job.source_updates_xml)
        config.set(section_name, 'repo_platform', update_job.source_repo_platform)
        config.set(section_name, 'repo_specifier', update_job.source_repo_specifier)
        config.set(section_name, 'repo_update_state', update_job.repo_update_state)
        config.set(section_name, 'target_updates_xml', update_job.target_updates_xml)
        config.write(cfgfile)
    cfgfile.close()


###############################
# Collect Updates.xml files
###############################
def collect_files(directory, file_name):
    file_list = []
    for root, dummy, files in os.walk(directory):
        for basename in files:
            if fnmatch.fnmatch(basename, file_name):
                filename = os.path.join(root, basename)
                file_list.append(filename)
    return file_list


###############################
# Function
###############################
def locate_directory(base_dir, dir_name):
    for root, dirs, dummy in os.walk(base_dir):
        for basename in dirs:
            if fnmatch.fnmatch(basename, dir_name):
                fulldirname = os.path.join(root, basename)
                # return the first match
                return fulldirname
    return ''


###############################
# Function
###############################
def locate_file(directory, file_name):
    for root, dummy, files in os.walk(directory):
        for basename in files:
            if fnmatch.fnmatch(basename, file_name):
                filename = os.path.join(root, basename)
                # return the first match
                return filename
    return ''


###############################
# Generate new update jobs from
# found Updates.xml files
###############################
def parse_new_update_jobs(update_xml_files):
    update_jobs = []
    for update_xml_file in update_xml_files:
        path_remainder = update_xml_file.split(ONLINE_REPOSITORY_ROOT_NAME)[1]
        path_remainder = path_remainder.split(ONLINE_REPOSITORY_META_FILE_NAME)[0]
        repo_platform = path_remainder.split('/')[1]
        repo_specifier = path_remainder.split(repo_platform)[1]
        # create new update job
        section_name_remainder = update_xml_file.replace(os.sep, '').replace('.', '') # unique string
        update_job = UpdateJob('UpdateJob.' + section_name_remainder, update_xml_file, repo_platform, repo_specifier, UpdateState.initial)
        update_jobs.append(update_job)
    # validate
    for item in update_jobs:
        item.validate()
    return update_jobs


###############################
# Function
###############################
def is_fresh_update_package(path):
    # check if contains only Updates.xml file, nothing else
    file_list = os.listdir(path)
    updates_xml_found = False
    file_count = 0
    for name in file_list:
        file_count += 1
        if name == ONLINE_REPOSITORY_META_FILE_NAME:
            updates_xml_found = True
    if updates_xml_found and file_count > 1:
        return True
    return False


###############################
# Function
###############################
def merge_update_jobs(pending_update_jobs, loaded_update_jobs):
    merged_jobs = []
    for pending_job in pending_update_jobs:
        for loaded_job in loaded_update_jobs:
            if loaded_job.source_updates_xml == pending_job.source_updates_xml:
                # filter out those jobs loaded from conf file which are superseded
                # by newer jobs in pending area as pending area always has the latest
                # update jobs
                if is_fresh_update_package(os.path.dirname(pending_job.source_updates_xml)):
                    loaded_job.flush = True
                else:
                    pending_job.flush = True
    combined_list_with_duplicates = pending_update_jobs + loaded_update_jobs
    # ignore duplicates
    for job in combined_list_with_duplicates:
        if not job.flush:
            merged_jobs.append(job)
    # generate unique id for interactive menus
    for i, _ in enumerate(merged_jobs):
        merged_jobs[i].temp_id = i
    # sanity check for duplicates
    fail_if_duplicate_found(merged_jobs)
    return merged_jobs


###############################
# Function
###############################
def fail_if_duplicate_found(update_job_list):
    for item in update_job_list:
        count = 0
        for item2 in update_job_list:
            if item.source_updates_xml == item2.source_updates_xml:
                count += 1
        if count > 1:
            sys.exit('*** Internal Error - Duplicate update job found for: {0}'.format(item.source_updates_xml))


###############################
# Function
###############################
def match_update_jobs_with_target_repository(update_jobs, target_repo_root):
    temp = []
    for update_job in update_jobs:
        # locate matching target platform first (linux_x64, linux_x86, mac_x64, windows_x86)
        match = platform_base_dir = locate_directory(target_repo_root, update_job.source_repo_platform)
        if not match:
            sys.exit('*** Internal Error - Unable to locate matching target platform for: {0}'.format(update_job.source_updates_xml))
        repo_specifiers = filter(None, update_job.source_repo_specifier.split('/'))
        for item in repo_specifiers:
            match = locate_directory(match, item)
        target_updates_xml = ''
        # given repsitory (directory) exists i.e. we update existing repository
        if match:
            target_updates_xml = locate_file(match, ONLINE_REPOSITORY_META_FILE_NAME)
        # if the target repo did not exist or was in 'ongoing' state (i.e. no Updates.xml present yet)
        # then try to figure out the Updates.xml path
        if not target_updates_xml:
            target_updates_xml = platform_base_dir + update_job.source_updates_xml.split(update_job.source_repo_platform)[1]
        update_job.target_updates_xml = target_updates_xml
        temp.append(update_job)
    return temp


###############################
# Function
###############################
def collect_update_info(update_info_conf_file, update_source_root_dir, target_repo_root):
    # (1) find all Updates.xml files under "update_source_root_dir" first i.e. possible updates
    update_xml_files = collect_files(update_source_root_dir, ONLINE_REPOSITORY_META_FILE_NAME)
    # (2) generate new update jobs from found Updates.xml files
    new_update_jobs = parse_new_update_jobs(update_xml_files)
    # (3) check from previous "update_info_conf_file" (if exists) if we had
    # previous pending updates ongoing
    old_update_jobs = []
    if update_info_conf_file:
        old_update_jobs = read_update_job_info(update_info_conf_file)
    # (4) "merge" new update jobs into ongoing update jobs
    merged_update_jobs = merge_update_jobs(new_update_jobs, old_update_jobs)
    # (5) match update jobs with target repositories
    final_update_jobs = match_update_jobs_with_target_repository(merged_update_jobs, target_repo_root)
    return final_update_jobs


###############################
# Function
###############################
def count_update_jobs_by_state(update_jobs, repo_update_state):
    count = 0
    for item in update_jobs:
        if item.repo_update_state == repo_update_state:
            count += 1
    return count


###############################
# Function
###############################
def list_updates_with_status(update_jobs, status):
    print('')
    print('------------------------------------------------')
    print('Available repository updates with status: {0}'.format(status))
    print('')
    for update_job in update_jobs:
        if update_job.repo_update_state == status:
            print('  * {0}'.format(os.path.dirname(update_job.source_updates_xml)))
    print('')


###############################
# Function
###############################
def print_selection_details(update_jobs, id_number):
    for i, _ in enumerate(update_jobs):
        if update_jobs[i].temp_id == id_number:
            print('')
            print('--------------------------------')
            print('Platform:       {0}'.format(update_jobs[i].source_repo_platform))
            print('Repo specifier: {0}'.format(update_jobs[i].source_repo_specifier))
            print('Target:         {0}'.format(os.path.dirname(update_jobs[i].target_updates_xml)))
            print('State:          {0}'.format(update_jobs[i].repo_update_state))
            print('')


###############################
# Function
###############################
def do_execute_updates(update_jobs, update_state, update_function):
    while (True):
        count = count_update_jobs_by_state(update_jobs, update_state)
        if not count:
            return
        print('')
        print('Available update jobs with state [{0}]: {1}'.format(update_state, count))
        print('')
        for i, _ in enumerate(update_jobs):
            if update_jobs[i].repo_update_state == update_state:
                print('================================')
                print('{0}:'.format(update_jobs[i].temp_id))
                print('Source: {0}'.format(os.path.dirname(update_jobs[i].source_updates_xml)))
                print('Target: {0}'.format(os.path.dirname(update_jobs[i].target_updates_xml)))
        print('')

        answer = ask_number_input('Enter number which item to update:')
        print('')
        if (answer < 0):
            return
        print_selection_details(update_jobs, answer)

        questions = []
        questions.append([1,'Confirm update the selected item?'])
        questions.append([5,'Cancel'])
        result = ask_enumerated_user_input(questions)
        print('')
        if (result == 1):
            update_function(answer, update_jobs)
        if (result == 5):
            return


###############################
# Function
###############################
def flush_finished_updates(update_jobs):
    while (True):
        print('')
        print('----------------------------')
        print('Old finished update jobs:')
        print('')
        for i, _ in enumerate(update_jobs):
            if update_jobs[i].repo_update_state == UpdateState.done:
                print('================================')
                print('{0}:'.format(update_jobs[i].temp_id))
                print('Source: {0}'.format(os.path.dirname(update_jobs[i].source_updates_xml)))
                print('Target: {0}'.format(os.path.dirname(update_jobs[i].target_updates_xml)))
        print('')
        print('Remove the listed update jobs from used configuration file?')
        questions = []
        questions.append([1,'Yes'])
        questions.append([9,'No'])
        result = ask_enumerated_user_input(questions)
        print('')
        if (result == 1):
            to_remove = [i for i, job in enumerate(update_jobs) if job.repo_update_state == UpdateState.done]
            for index in reversed(to_remove): # start at the end to avoid recomputing offsets
                del update_jobs[index]
            # Save changed update job status to config file
            store_update_job_info(ONLINE_UPDATE_JOB_CONFIG, update_jobs)
            return
        if (result == 9):
            return


###############################
# Move repository data files
###############################
def do_update_repository_data_files(id_num, update_jobs, update_all=False):
    for i, _ in enumerate(update_jobs):
        if update_jobs[i].repo_update_state != UpdateState.initial:
            continue
        if update_all or update_jobs[i].temp_id == id_num:
            print('Updating data files')
            # initial update i.e. only data files should be updated i.e. copied
            # (1) sanity check
            source_repo_path = os.path.dirname(update_jobs[i].source_updates_xml).split(ONLINE_REPOSITORY_ROOT_NAME)[1]
            target_repo_path = os.path.dirname(update_jobs[i].target_updates_xml).split(ONLINE_REPOSITORY_ROOT_NAME)[1]
            if not source_repo_path == target_repo_path:
                print('*** Fatal error! Source and target paths do not seem to match correctly for the update?')
                print('Source: {0}'.format(source_repo_path))
                print('Target: {0}'.format(target_repo_path))
                sys.exit(-1)
            # (2) does destination directory exist?
            target_dir = os.path.dirname(update_jobs[i].target_updates_xml)
            if not os.path.exists(target_dir):
                print('Destination directory does not exist, creating: {0}'.format(target_dir))
                os.makedirs(target_dir)
            # (3) copy data files (only)
            source_dir = os.path.dirname(update_jobs[i].source_updates_xml)
            safe_move_data_files_recursive(source_dir, target_dir)
            # (4) update state
            update_jobs[i].repo_update_state = UpdateState.ongoing
            # (5) Save changed update job status to config file
            store_update_job_info(ONLINE_UPDATE_JOB_CONFIG, update_jobs)
            print('Updating data files done')


###############################
# Move repository meta data files
###############################
def do_update_repository_meta_files(id_num, update_jobs, update_all=False):
    for i, _ in enumerate(update_jobs):
        if update_jobs[i].repo_update_state != UpdateState.ongoing:
            continue
        if update_all or update_jobs[i].temp_id == id_num:
            print('Updating meta files')
            # initial update i.e. only data files should be updated i.e. copied
            source_updates_xml = update_jobs[i].source_updates_xml
            target_updates_xml = update_jobs[i].target_updates_xml
            # (1) sanity check
            if not os.path.isfile(source_updates_xml):
                sys.exit('*** Fatal error! Source Updates.xml file not existing: {0}'.format(source_updates_xml))
            target_dir = os.path.dirname(update_jobs[i].target_updates_xml)
            if not os.path.exists(target_dir):
                sys.exit('*** Fatal error! Destination directory does not exist: {0}'.format(target_dir))
            # (2) Backup old Updates.xml file if exists
            is_existing_repository = os.path.isfile(target_updates_xml)
            if is_existing_repository:
                backup_filename = target_updates_xml + '_backup_' + strftime('%Y%m%d%H%M%S', gmtime())
                os.rename(target_updates_xml, backup_filename)
            # (3) Move new Updates.xml in place
            os.rename(source_updates_xml, target_updates_xml)
            if is_existing_repository:
                # (4) Save backup
                os.rename(backup_filename, target_updates_xml + '_backup_official_' + strftime('%Y%m%d%H%M%S', gmtime()))
            # (5) Remove empty source directory
            delete_directory_if_empty(os.path.dirname(update_jobs[i].source_updates_xml))
            # (6) update state
            update_jobs[i].repo_update_state = UpdateState.done
            # (7) Save changed update job status to config file
            store_update_job_info(ONLINE_UPDATE_JOB_CONFIG, update_jobs)
            print('Updating meta files done')


###############################
# Function
###############################
def safe_move_data_files_recursive(srcdir, dstdir):
    srcnames = os.listdir(srcdir)
    for name in srcnames:
        srcfname = os.path.join(srcdir, name)
        dstfname = os.path.join(dstdir, name)
        if os.path.isdir(srcfname) and not os.path.islink(srcfname):
            if not os.path.exists(dstfname):
                os.mkdir(dstfname)
            safe_move_data_files_recursive(srcfname, dstfname)
            delete_directory_if_empty(srcfname)
        elif name != ONLINE_REPOSITORY_META_FILE_NAME:
            if os.path.basename(srcfname) == os.path.basename(dstfname):
                if os.path.isfile(dstfname):
                    # we may be copying over the same files. E.g. "/tools_mingw" where we may update
                    # only one component but the rest are the same. As in practice we swap repo
                    # directories so we may end up copying over the existing files. Then we must ensure that
                    # the files we override are the same i.e. hash checksums match
                    mdsum_source = hashlib.sha256(open(srcfname, 'rb').read()).digest()
                    mdsum_dest = hashlib.sha256(open(dstfname, 'rb').read()).digest()
                    if mdsum_source != mdsum_dest:
                        print('*** Fatal! Source: {0} Destination {1}'.format(srcdir, dstdir))
                        print('*** Preventing accidental data file override. Can not override a file with same filename (and version) but different content. Hash check sums do not match. Aborting...')
                        sys.exit(-1)
            os.rename(srcfname, dstfname)


###############################
# Function
###############################
def delete_directory_if_empty(dir_name):
    try:
        os.rmdir(dir_name)
    except OSError as ex:
        if ex.errno != errno.ENOTEMPTY:
            print('*** Error while trying to delete directory, not empty: {0}, {1}'.format(ex.filename, ex.strerror))


###############################
# Function
###############################
def chunk_reader(fobj, chunk_size=1024):
    """Generator that reads a file in chunks of bytes"""
    while True:
        chunk = fobj.read(chunk_size)
        if not chunk:
            return
        yield chunk


#############################################################################################
# Interactive menu stuff
#############################################################################################
def show_main_menu(update_jobs):
    print('--------------------------------------------------------')
    print('Online Repository update tool. Available updates: {0}'.format(len(update_jobs)))
    while (True):
        print('')
        if len(update_jobs) <= 0:
            print('Nothing to do...')
            return

        initial_update_job_count = count_update_jobs_by_state(update_jobs, UpdateState.initial)
        ongoing_update_job_count = count_update_jobs_by_state(update_jobs, UpdateState.ongoing)
        finished_update_job_count = count_update_jobs_by_state(update_jobs, UpdateState.done)
        print('New updates found:      {0}'.format(initial_update_job_count))
        print('Ongoing updates found:  {0}'.format(ongoing_update_job_count))
        print('Finished updates found: {0}'.format(finished_update_job_count))

        questions = []
        if initial_update_job_count:
            questions.append([1,'List    NEW updates'])
            questions.append([2,'Perform NEW updates'])
        if ongoing_update_job_count:
            questions.append([3,'List    ONGOING updates'])
            questions.append([4,'Perform ONGOING updates'])
        if finished_update_job_count:
            questions.append([5,'List    FINISHED updates'])
            questions.append([6,'Clear   FINISHED updates'])
        questions.append([9,'Exit'])

        result = ask_enumerated_user_input(questions)
        print('')
        # exit
        if (result == 9):
            return
        # list
        if (result == 1):
            list_updates_with_status(update_jobs, UpdateState.initial)
        if (result == 3):
            list_updates_with_status(update_jobs, UpdateState.ongoing)
        if (result == 5):
            list_updates_with_status(update_jobs, UpdateState.done)
        # perform updates
        if (result == 2):
            do_execute_updates(update_jobs, UpdateState.initial, do_update_repository_data_files)
        if (result == 4):
            do_execute_updates(update_jobs, UpdateState.ongoing, do_update_repository_meta_files)
        # clear old finished updated from config file
        if (result == 6):
            flush_finished_updates(update_jobs)


###############################
# Function
###############################
def is_number(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


###############################
# Aks user input
###############################
def ask_enumerated_user_input(question_list):
    while (True):
        print('')
        allowed_answers = []
        for item in question_list:
            print('{0}: {1}'.format(item[0], item[1]))
            allowed_answers.append(item[0])
        var = raw_input("Selection: ")
        if is_number(var) and int(var) in allowed_answers:
            return int(var)


###############################
# Aks user input
###############################
def ask_number_input(question):
    print('')
    while(True):
        print(question)
        print('Cancel: c')
        var = raw_input("Selection: ")
        if var in ['c', 'C']:
            return -1
        if is_number(var) and int(var) >= 0:
            return int(var)



###############################
# Function
###############################
def generate_test_update_job_info():
    update_jobs = []
    config = ConfigParser.ConfigParser()
    section_name = 'UpdateJob.' + 'test_1'
    config.add_section(section_name)
    config.set(section_name, 'updates_xml', '/base_dir/foo/bar/qtsdkrepository/linux_x64/desktop/qt5/Updates.xml')
    config.set(section_name, 'repo_platform', 'linux_x64')
    config.set(section_name, 'repo_specifier', '/desktop/qt5')
    config.set(section_name, 'repo_update_state', UpdateState.initial)
    update_jobs.append(UpdateJob(config, section_name))

    section_name = 'UpdateJob.' + 'test_2'
    config.add_section(section_name)
    config.set(section_name, 'updates_xml', '/base_dir/foo/bar/qtsdkrepository/linux_x64/desktop/tools_maintenance/Updates.xml')
    config.set(section_name, 'repo_platform', 'linux_x64')
    config.set(section_name, 'repo_specifier', '/desktop/tools_maintenance')
    config.set(section_name, 'repo_update_state', UpdateState.initial)
    update_jobs.append(UpdateJob(config, section_name))

    section_name = 'UpdateJob.' + 'test_3'
    config.add_section(section_name)
    config.set(section_name, 'updates_xml', '/base_dir/foo/bar/qtsdkrepository/linux_x64/android/qt5/Updates.xml')
    config.set(section_name, 'repo_platform', 'linux_x64')
    config.set(section_name, 'repo_specifier', '/android/qt5')
    config.set(section_name, 'repo_update_state', UpdateState.initial)
    update_jobs.append(UpdateJob(config, section_name))

    return update_jobs


###############################
# Set and get cmd line parser
###############################
def get_cmd_line_parser():
    parser = argparse.ArgumentParser(prog = os.path.basename(sys.argv[0]),
        add_help=True, description="Update Qt Installer-Framework based online repositories", formatter_class=argparse.RawTextHelpFormatter)
    parser.epilog = "This script can be used to update online repositories generated with Qt Installer-Framework."\
        "The actual purpose for this tool is to ease out online updates in mirrored production servers where you have no control" \
        "in which order files get mirrored. For Qt Installer-Framework we must ensure the data files (*.7z) are in sync first before" \
        "meta files (Updates.xml) can be put in place as the meta files refer to the data files." \
        "The script allows the user to perform updates in phases. In first phase the user can update only the data files." \
        "In the second phase the user can update the meta files for those components that had the data files updated previously." \
        "The script saves component status information into configuration file so it can continue from previous time." \
        "".format(os.path.basename(sys.argv[0]))

    parser.add_argument('--pending_repo_root', help="Source root dir for new online repository components", required=True)
    parser.add_argument('--target_repo_root', help="Destination root dir where to perform the update", required=True)
    parser.add_argument('--update_info_conf', help="Config file defining existing/ongoing update jobs", required=False, default=DEFAULT_ONLINE_UPDATE_JOB_FILE_NAME)
    parser.add_argument('--force_initial_updates', help="Perform all available initial update jobs automatically", action='store_true', default=False)
    parser.add_argument('--force_ongoing_updates', help="Perform all available ongoing update jobs automatically", action='store_true', default=False)
    return parser.parse_args()


###############################
# Main
###############################
if __name__ == "__main__":
    cmd_line_parser = get_cmd_line_parser()
    update_jobs = collect_update_info(cmd_line_parser.update_info_conf, cmd_line_parser.pending_repo_root, cmd_line_parser.target_repo_root)
    ONLINE_UPDATE_JOB_CONFIG = cmd_line_parser.update_info_conf
    show_menu = True
    # show main menu and start interactive mode
    if cmd_line_parser.force_initial_updates:
        do_update_repository_data_files(None, update_jobs, True)
        show_menu = False
    if cmd_line_parser.force_ongoing_updates:
        do_update_repository_meta_files(None, update_jobs, True)
        show_menu = False
    if show_menu:
        show_main_menu(update_jobs)
    # store changed update job states to config file
    store_update_job_info(cmd_line_parser.update_info_conf, update_jobs)




