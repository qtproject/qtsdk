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
import platform
import sys
import unittest
from fileinput import FileInput
from shutil import rmtree
from tempfile import mkdtemp

from create_installer import parse_package_finalize_items
from patch_qt import (
    patch_absolute_lib_paths_from_line,
    patch_qconfig_pri_from_line,
    patch_qmake_prl_build_dir_from_line,
    patch_qt_edition,
)
from runner import do_execute_sub_process


class TestPackaging(unittest.TestCase):

    def test_patch_absolute_lib_paths(self) -> None:
        test_data = (("QMAKE_LIBS_ZLIB = /opt/android/android-ndk-r18b/platforms/android-21/arch-arm64/usr/lib/libz.so",
                      "QMAKE_LIBS_ZLIB = -lz",
                      "pri"),
                     ("QMAKE_LIBS_GTK3 = /lib64/libgtk-3.so /lib64/libgdk-3.so /lib64/libatk-1.0.so /lib64/libgio-2.0.so /lib64/libpangocairo-1.0.so /lib64/libgdk_pixbuf-2.0.so /lib64/libcairo-gobject.so /lib64/libpango-1.0.so /lib64/libcairo.so /lib64/libgobject-2.0.so /lib64/libglib-2.0.so",
                      "QMAKE_LIBS_GTK3 = -lgtk-3 -lgdk-3 -latk-1.0 -lgio-2.0 -lpangocairo-1.0 -lgdk_pixbuf-2.0 -lcairo-gobject -lpango-1.0 -lcairo -lgobject-2.0 -lglib-2.0",
                      "pri"),
                     ("QMAKE_PRL_LIBS = /opt/android/android-ndk-r18b/sources/cxx-stl/llvm-libc++/libs/arm64-v8a/libc++.so.21 /lib64/libglib-2.0.so",
                      "QMAKE_PRL_LIBS = -lc++ -lglib-2.0",
                      "prl"),
                     ("QMAKE_PRL_LIBS = -LC:\\opensslx86\\lib -L$$[QT_INSTALL_LIBS] $$[QT_INSTALL_LIBS]\\Qt5Cored.lib",
                      "QMAKE_PRL_LIBS = -LC:\\opensslx86\\lib -L$$[QT_INSTALL_LIBS] $$[QT_INSTALL_LIBS]\\Qt5Cored.lib",
                      "prl"),
                     ("QMAKE_PRL_LIBS = -LC:\\openssl\\lib \"C:\\Program Files (x86)\\Windows Kits\\10\\lib\\10.0.16299.0\\um\\x64\\shell32.lib\" $$[QT_INSTALL_LIBS]\\Qt5Cored.lib",
                      "QMAKE_PRL_LIBS = -LC:\\openssl\\lib \"-lshell32\" $$[QT_INSTALL_LIBS]\\Qt5Cored.lib",
                      "prl"),
                     ("QMAKE_PRL_LIBS = -LC:\\openssl\\lib \"C:\\Program Files (x86)\\Windows Kits\\10\\lib\\10.0.16299.0\\um\\x64\\shell32.foobar\" $$[QT_INSTALL_LIBS]\\Qt5Cored.foobar",
                      "QMAKE_PRL_LIBS = -LC:\\openssl\\lib \"C:\\Program Files (x86)\\Windows Kits\\10\\lib\\10.0.16299.0\\um\\x64\\shell32.foobar\" $$[QT_INSTALL_LIBS]\\Qt5Cored.foobar",
                      "prl"),
                     ("QMAKE_PRL_LIBS = $$[QT_INSTALL_LIBS]/qtfreetyped.lib \"C:\\Program Files (x86)\\Windows Kits\\10\\lib\\10.0.16299.0\\um\\x86/dwrite.lib\"",
                      "QMAKE_PRL_LIBS = $$[QT_INSTALL_LIBS]/qtfreetyped.lib \"-ldwrite\"",
                      "prl"),
                     ("_qt5gui_find_extra_libs(EGL \"c:/Utils/Android/android-ndk-r18b/platforms/android-16/arch-x86/usr/lib/libEGL.so\" \"\" \"\")",
                      "_qt5gui_find_extra_libs(EGL \"EGL\" \"\" \"\")",
                      "cmake"),
                     ("_qt5gui_find_extra_libs(EGL \"/opt/android/android-ndk-r18b/platforms/android-21/arch-arm64/usr/lib/libEGL.so\" \"\" \"\")",
                      "_qt5gui_find_extra_libs(EGL \"EGL\" \"\" \"\")",
                      "cmake"),
                     ("get_filename_component(_qt5Gui_install_prefix \"${CMAKE_CURRENT_LIST_DIR}/../../../\" ABSOLUTE)",
                      "get_filename_component(_qt5Gui_install_prefix \"${CMAKE_CURRENT_LIST_DIR}/../../../\" ABSOLUTE)",
                      "cmake"),
                     ("/Applications/Xcode10.app/Contents/Developer/Platforms/iPhoneOS.platform/Developer/SDKs/iPhoneOS12.1.sdk/usr/lib/libz.tbd -framework OpenGLES",
                      "-lz -framework OpenGLES",
                      "prl"))

        for data in test_data:
            result = patch_absolute_lib_paths_from_line(data[0], data[2])
            self.assertEqual(result, data[1], f"Failed to patch: [{data[0]}] as: [{data[1]}]")

    def test_patch_qmake_prl_build_dir_from_line(self) -> None:
        test_data = (("QMAKE_PRL_BUILD_DIR = /foo/bar", ""),
                     ("QMAKE_PRL_BUILD_DIR=   /foo/bar", ""),
                     ("foo bar = /foo/bar", "foo bar = /foo/bar"))

        for data in test_data:
            result = patch_qmake_prl_build_dir_from_line(data[0])
            self.assertEqual(result, data[1], f"Failed to patch: [{data[0]}] as: [{data[1]}]")

    def test_patch_qconfig_pri_from_line(self) -> None:
        test_data = (("QMAKE_DEFAULT_LIBDIRS = /foo/bar", "QMAKE_DEFAULT_LIBDIRS ="),
                     ("QMAKE_DEFAULT_INCDIRS =   /foo/bar", "QMAKE_DEFAULT_INCDIRS ="),
                     ("foo bar = /foo/bar", "foo bar = /foo/bar"))

        for data in test_data:
            result = patch_qconfig_pri_from_line(data[0])
            self.assertEqual(result, data[1], f"Failed to patch: [{data[0]}] as: [{data[1]}]. Got: [{result}]")

    def test_parse_package_finalize_items(self) -> None:
        test_data = (("set_executable=licheck64, foo=bar, set_executable=something", "set_executable", ["licheck64", "something"]),
                     ("set_executable=licheck64,foo=bar,   set_executable = something", "set_executable", ["licheck64", "something"]),
                     ("set_executable=licheck64", "set_executable", ["licheck64"]))

        for data in test_data:
            match_count = 0
            for item in parse_package_finalize_items(data[0], data[1]):
                self.assertIn(item, data[2])
                match_count += 1
            self.assertEqual(match_count, len(data[2]))

    def test_patch_qt_edition(self) -> None:
        temp_dir = mkdtemp(dir=os.getcwd())
        temp_file = os.path.join(temp_dir, "qconfig.pri")

        try:
            with open(temp_file, "a", encoding="utf-8") as handle:
                handle.write("something foo\n")
                handle.write("QT_EDITION = foobar\n")
                handle.write("nonsense\n")

            licheck_name = "licheck_foo"
            release_timestamp = "11223344"
            patch_qt_edition(temp_dir, licheck_name, release_timestamp)

            expected_data = []
            expected_data.append("something foo")
            expected_data.append("QT_EDITION = Enterprise")
            expected_data.append("QT_LICHECK = " + licheck_name)
            expected_data.append("QT_RELEASE_DATE = " + release_timestamp)
            expected_data.append("nonsense")

            idx = 0
            for line in FileInput(temp_file, inplace=False):
                print(f"Received data: [{line.strip()}] expected data: [{expected_data[idx]}]")
                self.assertEqual(line.strip(), expected_data[idx], f"Received data: [{line}] differs from expected data: [{expected_data[idx]}]")
                idx += 1
        finally:
            rmtree(temp_dir)

    @unittest.skipUnless(os.environ.get("PKG_TEST_QT_CONFIG_BASE_PATH"), "Skipping because 'PKG_TEST_QT_CONFIG_BASE_PATH' is not set")
    @unittest.skipUnless(os.environ.get("PKG_TEST_QT_ARTIFACTS_URL"), "Skipping because 'PKG_TEST_QT_CONFIG_BASE_PATH' is not set")
    @unittest.skipUnless(os.environ.get("PKG_TEST_QT_IFW_TOOL_URL"), "Skipping because 'PKG_TEST_QT_IFW_TOOL_URL' is not set")
    def test_create_installer(self) -> None:
        extension = '.run' if platform.system().lower().startswith('linux') else ''
        tests_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(os.environ.get("PKG_TEST_QT_CONFIG_BASE_PATH", ""), "offline_installer_jobs", "5.9.3")
        offline_jobs = os.listdir(path)
        for offline_job in offline_jobs:
            cmd_args = [sys.executable, '-u', os.path.join(tests_dir, 'create_installer.py')]
            cmd_args = cmd_args + ['-c', os.environ.get("PKG_TEST_QT_CONFIG_BASE_PATH", "")]
            cmd_args = cmd_args + ['-f', os.path.join(path, offline_job)]
            cmd_args = cmd_args + ['--offline']
            cmd_args = cmd_args + ['-l', 'enterprise']
            cmd_args = cmd_args + ['-u', os.environ.get("PKG_TEST_QT_ARTIFACTS_URL", "")]
            cmd_args = cmd_args + ['--ifw-tools=' + os.environ.get("PKG_TEST_QT_IFW_TOOL_URL", "")]
            cmd_args = cmd_args + ['--preferred-installer-name=' + offline_job]
            cmd_args = cmd_args + ['--dry-run']
            try:
                do_execute_sub_process(cmd_args, os.getcwd())
            except Exception as error:
                self.fail(f"Failed to execute: [{' '.join(cmd_args)}] -> {str(error)}")
            self.assertTrue(os.path.exists(os.path.join(tests_dir, 'installer_output', offline_job + extension)), "No installers generated")


if __name__ == '__main__':
    unittest.main()
