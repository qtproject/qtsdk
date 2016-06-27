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
## ensure the GNU General Public Lhttps://www.google.fi/icense version 3.0 requirements will be
## met: http://www.gnu.org/copyleft/gpl.html.
##
##
## $QT_END_LICENSE$
##
#############################################################################

from __future__ import print_function
import os
import shutil
import sys
import multiprocessing
import bldinstallercommon
bldinstallercommon.init_common_module(os.path.dirname(os.path.realpath(__file__)))

def handle_module_doc_build():
    if not bldinstallercommon.is_linux_platform():
        raise RuntimeError('*** Only Linux platform supported currently to perform doc builds. Aborting')
    if not os.environ.get('MODULE_NAME'):
        print('*** MODULE_NAME environment variable not defined. Unable to generate doc for this package.')
        return
    if not os.environ.get('MODULE_SRC_PACKAGE_URI'):
        print('*** MODULE_SRC_PACKAGE_URI environment variable not defined. Unable to generate doc for this package.')
        return
    if not os.environ.get('MODULE_DOC_BUILD_QT_PACKAGE_URI'):
        print('*** MODULE_DOC_BUILD_QT_PACKAGE_URI environment variable not defined. Unable to generate doc for this package.')
        return
    if not os.environ.get('MODULE_DOC_BUILD_QT_ICU_PACKAGE_URI'):
        print('*** MODULE_DOC_BUILD_QT_ICU_PACKAGE_URI environment variable not defined. Unable to generate doc for this package.')
        return
    module_src_package_uri = os.environ['MODULE_SRC_PACKAGE_URI']
    module_doc_build_qt_package_uri = os.environ['MODULE_DOC_BUILD_QT_PACKAGE_URI']
    module_doc_build_qt_dependency_package_uri = os.environ.get('MODULE_DOC_BUILD_QT_DEPENDENCY_PACKAGE_URI', '')
    module_doc_build_qt_icu_package_uri = os.environ['MODULE_DOC_BUILD_QT_ICU_PACKAGE_URI']
    # define some paths
    current_path = os.path.dirname(os.path.realpath(__file__))
    qt_package_path = os.path.join(current_path, 'doc_build_qt_package')
    if os.path.exists(qt_package_path):
        print('*** Deleted existing qt package directory (for doc build) before setting up the new one: '.format(qt_package_path))
        shutil.rmtree(qt_package_path)
    qt_icu_path = os.path.join(current_path, 'doc_build_qt_icu_package')
    if os.path.exists(qt_icu_path):
        print('*** Deleted existing qt icu directory (for doc build) before setting up the new one: '.format(qt_icu_path))
        shutil.rmtree(qt_icu_path)
    module_src_path = os.path.join(current_path, 'module_src_package')
    if os.path.exists(module_src_path):
        print('*** Deleted existing module package directory before setting up the new one: '.format(module_src_path))
        shutil.rmtree(module_src_path)
    bldinstallercommon.create_dirs(qt_package_path)
    bldinstallercommon.create_dirs(module_src_path)
    bldinstallercommon.create_dirs(qt_icu_path)
    # fetch module src package
    raw_name_module_src_package = module_src_package_uri.rsplit('/', 1)[-1] # get last item from array
    downloaded_module_archive = os.path.join(current_path, raw_name_module_src_package)
    if os.path.lexists(downloaded_module_archive):
        print('*** Deleted existing module src package: [{0}] before fetching the new one.{0}'.format(downloaded_module_archive))
        os.remove(downloaded_module_archive)
    print('Starting to download: {0}'.format(module_src_package_uri))
    bldinstallercommon.retrieve_url(module_src_package_uri, downloaded_module_archive)
    bldinstallercommon.extract_file(downloaded_module_archive, module_src_path)
    # fetch qt binary package
    raw_name_qt_bin_package = module_doc_build_qt_package_uri.rsplit('/', 1)[-1] # get last item from array
    downloaded_qt_bin_archive = os.path.join(current_path, raw_name_qt_bin_package)
    if os.path.lexists(downloaded_qt_bin_archive):
        print('*** Deleted existing qt binary package: [{0}] before fetching the new one.'.format(downloaded_qt_bin_archive))
        os.remove(downloaded_qt_bin_archive)
    print('Starting to download: {0}'.format(module_doc_build_qt_package_uri))
    bldinstallercommon.retrieve_url(module_doc_build_qt_package_uri, downloaded_qt_bin_archive)
    bldinstallercommon.extract_file(downloaded_qt_bin_archive, qt_package_path)
    # fetch qt dependency package (optional)
    if bldinstallercommon.is_content_url_valid(module_doc_build_qt_dependency_package_uri):
        raw_name_qt_bin_dependency_package = module_doc_build_qt_dependency_package_uri.rsplit('/', 1)[-1] # get last item from array
        downloaded_qt_dependency_bin_archive = os.path.join(current_path, raw_name_qt_bin_dependency_package)
        if os.path.lexists(downloaded_qt_dependency_bin_archive):
            print('*** Deleted existing qt binary dependency package: [{0}] before fetching the new one.'.format(downloaded_qt_dependency_bin_archive))
            os.remove(downloaded_qt_dependency_bin_archive)
        print('Starting to download: {0}'.format(module_doc_build_qt_dependency_package_uri))
        bldinstallercommon.retrieve_url(module_doc_build_qt_dependency_package_uri, downloaded_qt_dependency_bin_archive)
        bldinstallercommon.extract_file(downloaded_qt_dependency_bin_archive, qt_package_path)
    # fetch qt icu binary package
    raw_name_qt_icu_package = module_doc_build_qt_icu_package_uri.rsplit('/', 1)[-1] # get last item from array
    downloaded_qt_icu_archive = os.path.join(current_path, raw_name_qt_icu_package)
    if os.path.lexists(downloaded_qt_icu_archive):
        print('*** Deleted existing qt icu package: [{0}] before fetching the new one.'.format(downloaded_qt_icu_archive))
        os.remove(downloaded_qt_icu_archive)
    print('Starting to download: {0}'.format(module_doc_build_qt_icu_package_uri))
    bldinstallercommon.retrieve_url(module_doc_build_qt_icu_package_uri, downloaded_qt_icu_archive)
    qt_lib_directory = bldinstallercommon.locate_directory(qt_package_path, 'lib')
    bldinstallercommon.extract_file(downloaded_qt_icu_archive, qt_lib_directory)
    # patch Qt package
    qt_bin_directory = bldinstallercommon.locate_directory(qt_package_path, 'bin')
    if not os.path.exists(qt_bin_directory):
        raise IOError('*** Unable to locate bin directory from: %s' % qt_bin_directory)
    qtConfFile = open(os.path.join(qt_bin_directory, 'qt.conf'), "w")
    qtConfFile.write("[Paths]" + os.linesep)
    qtConfFile.write("Prefix=.." + os.linesep)
    qtConfFile.close()
    qt_directory = os.path.dirname(qt_bin_directory)
    bldinstallercommon.handle_component_rpath(qt_directory, 'lib')
    # locate tools
    qmake_binary = bldinstallercommon.locate_executable(qt_directory, 'qmake')
    print('Using qmake from: {0}'.format(qmake_binary))
    # locate module .pro file
    module_pro_file = bldinstallercommon.locate_file(module_src_path, '*.pro')
    # build module
    module_build_environment = dict(os.environ)
    module_build_environment["LD_LIBRARY_PATH"] = os.pathsep.join([os.path.join(qt_package_path, 'lib')] +
                                                        os.environ.get("LD_LIBRARY_PATH", "").split(os.pathsep))
    module_build_environment["QMAKESPEC"] = "linux-g++"
    cpu_count = ["-j" + str(multiprocessing.cpu_count() + 1)]
    print('Using .pro file from: {0}'.format(module_pro_file))
    bld_args = [qmake_binary, module_pro_file]
    bldinstallercommon.do_execute_sub_process(args=bld_args, execution_path=os.path.dirname(module_pro_file),
                                              abort_on_fail=False, extra_env=module_build_environment)
    bld_args = ['make'] + cpu_count
    bldinstallercommon.do_execute_sub_process(args=bld_args, execution_path=os.path.dirname(module_pro_file),
                                              abort_on_fail=False, extra_env=module_build_environment)
    # make docs
    bld_args = ['make', '-j1', 'docs']
    bldinstallercommon.do_execute_sub_process(args=bld_args, execution_path=os.path.dirname(module_pro_file),
                                              abort_on_fail=False, extra_env=module_build_environment)
    # make install docs
    module_doc_install_dir = module_src_path = os.path.join(current_path, 'module_doc_install_dir')
    bld_args = ['make', '-j1', 'install_docs', 'INSTALL_ROOT=' + module_doc_install_dir]
    bldinstallercommon.do_execute_sub_process(args=bld_args, execution_path=os.path.dirname(module_pro_file),
                                              abort_on_fail=False, extra_env=module_build_environment)
    # create archive
    doc_dir = bldinstallercommon.locate_directory(module_doc_install_dir, 'doc')
    if not os.path.exists(doc_dir):
        print('Warning! Doc archive not generated!')
        return
    archive_name = os.environ['MODULE_NAME'] + '-' + os.environ['LICENSE'] + '-doc-' + os.environ['MODULE_VERSION'] + '.7z'
    archive_path = os.path.join(current_path, 'doc_archives', archive_name)
    bld_args = ['7z', 'a', archive_path, 'doc']
    bldinstallercommon.do_execute_sub_process(args=bld_args, execution_path=os.path.dirname(doc_dir), abort_on_fail=False)
    if os.path.exists(archive_path):
        print('Doc archive generated successfully: {0}'.format(archive_path))

