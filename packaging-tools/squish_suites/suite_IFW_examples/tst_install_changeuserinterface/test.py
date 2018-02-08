# -*- coding: utf-8 -*-

###########################################################################
##
## Copyright (C) 2018 The Qt Company Ltd.
## Contact: https://www.qt.io/licensing/
##
## This file is part of the Qt Installer Framework.
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
###########################################################################

import os
from os.path import expanduser
import subprocess
import shlex
import sys
sys.path.append(os.path.join(os.pardir,os.pardir, "shared"))
import shared
import time


def info():
    test.log("#" * 50)
    test.log("Squish path: " + os.environ["SQUISH_PREFIX"])
    test.log("#" * 50 + "\n")

def main():
    info()
    shared.add_attachable_aut()
    time.sleep(7)
    home = os.path.expanduser("~")
    application_folder = "changeuserinterface" #folder where application resides
    executable = "installer"    #executable without filename extension eg. exe
    # abs path to application folder(folder of tested program)
    primary_test_install_dir = os.path.join(home, "IfwExamples")
    application_folder_path = os.path.join("ifw-src", "examples", application_folder)
    application_folder_path = os.path.normpath(os.path.join(os.path.abspath(__file__), os.path.pardir,os.path.pardir, os.path.pardir, os.path.pardir, application_folder_path))
    # Attempts to start and attach testable application
    test.log("Attempting to start and attach AUT")
    subprocess_handle = shared.attach_to_aut(application_folder_path, executable)
    if not subprocess_handle:
        return False

    # Actual beginning for test
    test.log("Clicking next button at welcome page.")
    clickButton(waitForObject(":Change Installer UI Example Setup.__qt__passive_wizardbutton1_QPushButton_2"))
    test.log("Appending _2 to installation path.")
    type(waitForObject(":Change Installer UI Example Setup.TargetDirectoryLineEdit_QLineEdit"), "_2")
    test.log("Clicking next button at installation path specification page.")
    clickButton(waitForObject(":Change Installer UI Example Setup.__qt__passive_wizardbutton1_QPushButton_2"))
    test.log("Clicking next button at component selection page.")
    clickButton(waitForObject(":Change Installer UI Example Setup.__qt__passive_wizardbutton1_QPushButton_2"))
    test.log("Clicking i agree radio button at license agreement page.")
    clickButton(waitForObject(":Change Installer UI Example Setup.AcceptLicenseRadioButton_QRadioButton"))
    test.log("Clicking next button at license agreement page.")
    clickButton(waitForObject(":Change Installer UI Example Setup.__qt__passive_wizardbutton1_QPushButton_2"))
    #Only win has this start menu thing
    if sys.platform.startswith("win"):
        test.log("Clicking next button at StartMenu Shortcut specification screen.")
        clickButton(waitForObject(":Change Installer UI Example Setup.__qt__passive_wizardbutton1_QPushButton_2"))
    test.log("Clicking install button at ready to install page.")
    clickButton(waitForObject(":Change Installer UI Example Setup.__qt__passive_wizardbutton1_QPushButton"))
    test.log("Clicking finish button at end page.")
    clickButton(waitForObject(":Change Installer UI Example Setup.qt_wizard_finish_QPushButton"))
    test.verify(os.path.exists(os.path.join(home, "IfwExamples", "changeuserinterface_2")), "installation folder exists")

    snooze(1)
    # Makes sure that application under test will not keep running after test.
    subprocess_handle.kill()
