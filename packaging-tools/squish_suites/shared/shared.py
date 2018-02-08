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
import sys
import shlex
import subprocess
import test
import testData
import object
import objectMap
import squishinfo
import squish
import squish_module_helper

def add_attachable_aut(name="teest",port=11233):
    test.log("Adding attachable aut to autlist")
    squish_module_helper.import_squish_symbols()
    if sys.platform.startswith("win"):
        subprocess.Popen([os.path.join(os.environ["SQUISH_PREFIX"], 'bin', 'squishserver.exe'), '--config',  'addAttachableAUT', name, str(port)])
    else:
        subprocess.Popen([os.path.join(os.environ["SQUISH_PREFIX"], 'bin', 'squishserver'), '--config',  'addAttachableAUT', name, str(port)])

def attach_to_aut(application_folder_path,
                   executable,
                   arguments_for_aut = "--uses-builtin-hook",
                   squish_path = os.path.join(os.environ["SQUISH_PREFIX"])):

    squish_module_helper.import_squish_symbols()
    start_aut_bin = os.path.join(squish_path, "bin", "startaut")
    if sys.platform.startswith("win"):
        executable += ".exe"
        start_aut_bin += ".exe"
    application_under_test = os.path.join(application_folder_path, executable)
    # builds absolute path to testable application
    test.log("Application under test: " + str(application_folder_path)+"/"+executable)
    test.log(str(start_aut_bin))
    if sys.platform.startswith("win"):
        start_aut_bin = start_aut_bin.replace("\\", "\\\\")
        application_under_test = application_under_test.replace("\\", "\\\\")
    start_aut_cmd = " ".join([start_aut_bin,arguments_for_aut,application_under_test]) # creates string for launching aut
    start_aut_cmd = shlex.split(start_aut_cmd) # Converts launch string to list as needed by Unix; Windows can use string or list.
    test.log("Subprocess call arguments", ' '.join(start_aut_cmd))
    test.log(start_aut_cmd[0])
    subprocess_handle = subprocess.Popen(start_aut_cmd, shell=False)
    if sys.platform.startswith("win"):
        snooze(5)
    else:
        snooze(1) # This delay is need to give time for application to start
    test.log("Attaching to application")
    testSettings.waitForObjectTimeout = 2000
# Attempts to attach to application under test, if it fails will close program.
    try:
        attachToApplication("teest") # Note that name teest comes from Applications source code (all examples use this at least for now)
    except Exception as e: # Handles failing to attach to application eg. log and kill.
        test.fatal("FAIL: failed to attach to application", str(e))
        subprocess_handle.kill()
        return None
    else:
        test.passes("Application successfully attached")
        return subprocess_handle
