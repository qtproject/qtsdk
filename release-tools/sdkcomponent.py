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

import os
import sys
import bldinstallercommon
from archiveresolver import ArchiveLocationResolver

IFW_DOWNLOADABLE_ARCHIVE_NAMES_TAG  = '//%IFW_DOWNLOADABLE_ARCHIVE_NAMES%'


class SdkComponent:
    """SdkComponent class contains all required info for one installable SDK component"""
    class DownloadableArchive:
        """DownloadableArchive subclass contains all required info about data packages for one SDK component"""
        def __init__(self, archive, package_name, archive_server_name, target_config, archive_location_resolver):
            self.archive_uri        = bldinstallercommon.config_section_map(target_config, archive)['archive_uri']
            self.package_strip_dirs = bldinstallercommon.safe_config_key_fetch(target_config, archive, 'package_strip_dirs')
            self.target_install_dir = bldinstallercommon.safe_config_key_fetch(target_config, archive, 'target_install_dir') # todo, is needed?
            self.rpath_target       = bldinstallercommon.safe_config_key_fetch(target_config, archive, 'rpath_target')
            self.archive_name       = bldinstallercommon.safe_config_key_fetch(target_config, archive, 'archive_name')
            self.nomalize_archive_uri(package_name, archive_server_name, archive_location_resolver)


        def nomalize_archive_uri(self, package_name, archive_server_name, archive_location_resolver):
            self.archive_uri = archive_location_resolver.resolve_full_uri(package_name, archive_server_name, self.archive_uri)


        def check_archive_data(self):
            if self.archive_uri.startswith('http'):
                res = bldinstallercommon.is_content_url_valid(self.archive_uri)
                if not res:
                    return '*** Archive check fail! ***\n*** Unable to locate archive: ' + self.archive_uri
            elif not os.path.isfile(self.archive_uri):
                return '*** Archive check fail! ***\n*** Unable to locate archive: ' + self.archive_uri


    def __init__(self, section_name, target_config, packages_full_path_list, archive_location_resolver):
        self.static_component           = bldinstallercommon.safe_config_key_fetch(target_config, section_name, 'static_component')
        self.root_component             = bldinstallercommon.safe_config_key_fetch(target_config, section_name, 'root_component')
        self.package_name               = section_name
        self.packages_full_path_list    = packages_full_path_list
        self.archives                   = bldinstallercommon.safe_config_key_fetch(target_config, section_name, 'archives')
        self.archives                   = self.archives.replace(' ', '')
        self.archive_server_name        = bldinstallercommon.safe_config_key_fetch(target_config, section_name, 'archive_server_name')
        self.downloadable_archive_list  = []
        self.target_install_base        = bldinstallercommon.safe_config_key_fetch(target_config, section_name, 'target_install_base')
        self.version                    = bldinstallercommon.safe_config_key_fetch(target_config, section_name, 'version')
        self.version_tag                = bldinstallercommon.safe_config_key_fetch(target_config, section_name, 'version_tag')
        self.package_default            = bldinstallercommon.safe_config_key_fetch(target_config, section_name, 'package_default')
        self.install_priority           = bldinstallercommon.safe_config_key_fetch(target_config, section_name, 'install_priority')
        self.sorting_priority           = bldinstallercommon.safe_config_key_fetch(target_config, section_name, 'sorting_priority')
        self.downloadable_arch_list_qs  = []
        self.pkg_template_dir           = ''
        self.sanity_check_error_msg     = ''
        self.target_config              = target_config
        self.archive_location_resolver  = archive_location_resolver


    def is_root_component(self):
        if self.root_component == 'yes' or self.root_component == 'true':
            return True
        return False

    def validate(self):
        # look up correct package template directory from list
        found = False
        for item in self.packages_full_path_list:
            template_full_path = os.path.normpath(item + os.sep + self.package_name)
            if os.path.exists(template_full_path):
                if not (found):
                    # take the first match
                    self.pkg_template_dir = template_full_path
                    found = True
                else:
                    # sanity check, duplicate template should not exist to avoid
                    # problems!
                    print '*** Found duplicate template for: ' + section_name
                    print '*** Only one template for package should exist!'
                    print '*** Fix your configuration! Abort!'
                    sys.exit(-1)
        self.parse_archives(self.target_config, self.archive_location_resolver)
        self.check_component_data(self.target_config)


    def check_component_data(self, target_config):
        if self.static_component:
            if not os.path.isfile(self.static_component):
                self.sanity_check_fail(self.package_name, 'Unable to locate given static package: ' + self.static_component)
                return
            # no more checks needed for static component
            return
        if not self.package_name:
            self.sanity_check_fail(self.package_name, 'Undefined package name?')
            return
        if self.archives and not self.target_install_base:
            self.sanity_check_fail(self.package_name, 'Undefined target_install_base?')
            return
        if self.version and not self.version_tag:
            self.sanity_check_fail(self.package_name, 'Undefined version_tag?')
            return
        if self.version_tag and not self.version:
            self.sanity_check_fail(self.package_name, 'Undefined version?')
            return
        if self.package_default not in ['true', 'false', 'script']:
            self.package_default = 'false'
        # check that package template exists
        if not os.path.exists(self.pkg_template_dir):
            self.sanity_check_fail(self.package_name, 'Package template dir does not exist: ' + self.pkg_template_dir)
            return
        # next check that archive locations exist
        for archive in self.downloadable_archive_list:
            error_msg = archive.check_archive_data()
            if error_msg:
                self.sanity_check_fail(self.package_name, error_msg)
                return


    def sanity_check_fail(self, component_name, message):
        self.sanity_check_error_msg = '*** Sanity check fail! ***\n*** Component: [' + component_name + ']\n*** ' + message


    def is_valid(self):
        if self.sanity_check_error_msg:
            return False
        else:
            return True


    def error_msg(self):
        return self.sanity_check_error_msg


    def parse_archives(self, target_config, archive_location_resolver):
        if self.archives:
            archives_list = self.archives.split(',')
            for archive in archives_list:
                # check that archive template exists
                if not target_config.has_section(archive):
                    print '*** Error! Given archive section does not exist in configuration file: ' + archive
                    print '*** Abort!'
                    sys.exit(-1)
                archive_obj = SdkComponent.DownloadableArchive(archive, self.package_name, self.archive_server_name, target_config, archive_location_resolver)
                self.downloadable_archive_list.append(archive_obj)


    def generate_downloadable_archive_list(self, downloadable_archive_list):
        """Generate java script code that is embedded into installscript.qs"""

        if self.downloadable_archive_list:
            output = ''
            for item in self.downloadable_archive_list:
                output = output + 'component.addDownloadableArchive(\"' + item.archive_name + '\");'

        temp_list = []
        temp_list.append([IFW_DOWNLOADABLE_ARCHIVE_NAMES_TAG, output])
        return temp_list


    def print_component_data(self):
        print '============================================================='
        print ' [' + self.package_name + ']'
        if self.static_component:
            print ' Static component:    ' + self.static_component
            return
        if self.root_component:
            print ' Root component:      ' + self.root_component
        print ' Target install base: ' + self.target_install_base
        print ' Version:             ' + self.version
        print ' Version tag:         ' + self.version_tag
        print ' Package default:     ' + self.package_default
        if self.downloadable_archive_list:
            print ' Archives:'
            for archive in self.downloadable_archive_list:
                print '   ---------------------------------------------------------------'
                print '   Downloadable archive name:  ' + archive.archive_name
                print '   Archive strip dirs:         ' + archive.package_strip_dirs
                print '   Archive target install dir: ' + archive.target_install_dir
                print '   Archive RPath target:       ' + archive.rpath_target
                print '   Archive URI:                ' + archive.archive_uri

