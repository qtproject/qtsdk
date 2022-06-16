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

import os
import bldinstallercommon
import pkg_constants
from urllib.parse import urlparse

SERVER_NAMESPACE = 'ArchiveRemoteLocation'
PACKAGE_REMOTE_LOCATION_RELEASE = 'release'
PACKAGE_ARCHIVE_TAG = 'ARCHIVE_TAG'


###############################
# class ArchiveLocationResolver
###############################
class ArchiveLocationResolver:
    """Helper class to resolve full URI for archive"""

    ######################################
    # inner class ArchiveRemoteLocation
    ######################################
    class ArchiveRemoteLocation:
        """Container class for server URL data"""

        ###############################
        # Constructor
        ###############################
        def __init__(self, server_name, server_base_url, server_base_path):
            self.server_name = server_name
            temp = server_base_url
            if not temp.endswith('/') and not server_base_path.startswith('/'):
                temp = temp + '/'
            temp = temp + server_base_path
            self.server_url = temp

    ###############################
    # Constructor
    ###############################
    def __init__(self, target_config, server_base_url_override, configurations_root_dir, key_substitution_list):
        """Init data based on the target configuration"""
        self.server_list = []
        self.pkg_templates_dir_list = []
        self.default_server = None
        self.configurations_root_dir = configurations_root_dir
        self.key_substitution_list = key_substitution_list
        # get packages tempalates src dir first
        pkg_templates_dir = os.path.normpath(bldinstallercommon.config_section_map(target_config, 'PackageTemplates')['template_dirs'])
        self.pkg_templates_dir_list = pkg_templates_dir.replace(' ', '').rstrip(',\n').split(',')
        # next read server list
        if server_base_url_override:
            server_obj = ArchiveLocationResolver.ArchiveRemoteLocation('default_server_name', server_base_url_override, '')
            self.server_list.append(server_obj)
        else:
            for section in target_config.sections():
                if section.startswith(SERVER_NAMESPACE):
                    server_name = section.split('.')[-1]
                    base_url = bldinstallercommon.safe_config_key_fetch(target_config, section, 'base_url')
                    base_path = bldinstallercommon.safe_config_key_fetch(target_config, section, 'base_path')
                    base_path.replace(' ', '')
                    # if base path is defined, then the following logic applies:
                    # if script is used in testclient mode fetch the packages from "RnD" location
                    # otherwise fetch packages from "release" location.
                    # If the base_path is not defined, use the address as-is
                    if base_path:
                        base_path = base_path + PACKAGE_REMOTE_LOCATION_RELEASE
                    server_obj = ArchiveLocationResolver.ArchiveRemoteLocation(server_name, base_url, base_path)
                    self.server_list.append(server_obj)
        if len(self.server_list) == 1:
            self.default_server = self.server_list[0]

    ###############################
    # Get full server URL by name
    ###############################
    def server_url_by_name(self, server_name):
        """Get server URL by name. If empty name given, return the default server (may be null)."""
        if not server_name:
            return self.default_server.server_url
        for server in self.server_list:
            if server.server_name == server_name:
                return server.server_url
        raise RuntimeError('*** Error! Unable to find server by name: %s' % server_name)

    ###############################
    # Get full server URI
    ###############################
    def resolve_full_uri(self, package_name, server_name, archive_uri):
        """Resolve the full URI in the following order
             1. is archive_uri a valid URI as such
             2. check if given archive_uri denotes a package under package templates directory
             3. check if given URI is valid full URL
             4. try to compose full URL
            return the resolved URI
        """
        # substitute key value pairs if any
        for item in self.key_substitution_list:
            temp = archive_uri.replace(item[0], item[1])
            if temp != archive_uri:
                archive_uri = temp
        # 1. check if given archive_uri denotes a package under package templates directory
        base_path = os.path.join(self.configurations_root_dir, pkg_constants.PKG_TEMPLATE_BASE_DIR_NAME)
        package_path = package_name + os.sep + 'data' + os.sep + archive_uri
        # find the correct template subdirectory
        for subdir in self.pkg_templates_dir_list:
            path_temp = os.path.join(base_path, subdir)
            if not os.path.isdir(path_temp):
                path_temp = path_temp.replace(os.sep + pkg_constants.PKG_TEMPLATE_BASE_DIR_NAME, '')
            if os.path.isdir(path_temp):
                temp = os.path.join(path_temp, package_path)
                if os.path.isfile(temp):
                    return temp
        # 2. check if given URI is valid full URL
        res = bldinstallercommon.is_content_url_valid(archive_uri)
        if res:
            return archive_uri
        else:
            parts = urlparse(archive_uri)
            if parts.scheme and parts.netloc:
                raise RuntimeError("Url: [%s] points to valid location but it is inaccessible." % (archive_uri))
        # 3. try to compose full URL
        temp = self.server_url_by_name(server_name)
        if not temp.endswith('/') and not archive_uri.startswith('/'):
            temp = temp + '/'
        temp = temp + archive_uri
        return temp

    ###############################
    # Print out server list
    ###############################
    def print_server_list(self):
        print('--------------------------------------------------')
        print(' Server list:')
        for server in self.server_list:
            print(' ---------------------------------------------')
            print(' Server name: ' + server.server_name)
            print(' Server url:  ' + server.server_url)
