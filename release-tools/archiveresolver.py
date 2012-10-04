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

SERVER_NAMESPACE                = 'ArchiveRemoteLocation'
PACKAGE_REMOTE_LOCATION_RELEASE = 'release'
PACKAGE_ARCHIVE_TAG             = 'ARCHIVE_TAG'


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
    def __init__(self, target_config, server_base_url_override, configurations_root_dir):
        """Init data based on the target configuration"""
        self.server_list = []
        self.pkg_templates_dir = ''
        self.default_server = None
        self.configurations_root_dir = configurations_root_dir
        # get packages tempalates src dir first
        self.pkg_templates_dir = os.path.normpath(bldinstallercommon.config_section_map(target_config,'WorkingDirectories')['packages_dir'])
        server_namespace = os.path.normpath(bldinstallercommon.config_section_map(target_config,'WorkingDirectories')['packages_dir'])
        # next read server list
        if server_base_url_override:
            server_obj  = ArchiveLocationResolver.ArchiveRemoteLocation('default_server_name', server_base_url_override, '')
            self.server_list.append(server_obj)
        else:
            for section in target_config.sections():
                if section.startswith(SERVER_NAMESPACE):
                    server_name = section.split('.')[-1]
                    base_url    = bldinstallercommon.safe_config_key_fetch(target_config, section, 'base_url')
                    base_path   = bldinstallercommon.safe_config_key_fetch(target_config, section, 'base_path')
                    base_path.replace(' ', '')
                    # if base path is defined, then the following logic applies:
                    # if script is used in testclient mode fetch the packages from "RnD" location
                    # otherwise fetch packages from "release" location.
                    # If the base_path is not defined, use the address as-is
                    if base_path:
                        base_path = base_path + PACKAGE_REMOTE_LOCATION_RELEASE
                    server_obj  = ArchiveLocationResolver.ArchiveRemoteLocation(server_name, base_url, base_path)
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
        print '*** Error! Unable to find server by name: ' + server_name
        sys.exit(-1)


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
        # source package specific, if archive_uri contains special tag, it means
        # that it's source package. Replace the suffix specified by the platform
        if archive_uri.endswith(PACKAGE_ARCHIVE_TAG):
            if bldinstallercommon.is_win_platform():
                archive_uri = archive_uri.replace(PACKAGE_ARCHIVE_TAG, 'zip')
            else:
                archive_uri = archive_uri.replace(PACKAGE_ARCHIVE_TAG, "tar.gz")
        # 1. the file exists, uri points to valid path on file system (or network share)
        if os.path.isfile(archive_uri):
            return archive_uri
        # 2. check if given archive_uri denotes a package under package templates directory
        temp = os.path.normpath(self.configurations_root_dir + os.sep + self.pkg_templates_dir + os.sep + package_name + os.sep + 'data' + os.sep + archive_uri)
        if os.path.isfile(temp):
            return temp
        # 3. check if given URI is valid full URL
        res = bldinstallercommon.is_content_url_valid(archive_uri)
        if res:
            return archive_uri
        # 4. try to compose full URL
        temp = self.server_url_by_name(server_name)
        if not temp.endswith('/') and not archive_uri.startswith('/'):
            temp = temp + '/'
        temp = temp + archive_uri
        return temp


    ###############################
    # Print out server list
    ###############################
    def print_server_list(self):
        print '--------------------------------------------------'
        print ' Server list:'
        for server in self.server_list:
            print ' ---------------------------------------------'
            print ' Server name: ' + server.server_name
            print ' Server url:  ' + server.server_url

