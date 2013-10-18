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

import itertools
import subprocess
import os

# http://stackoverflow.com/questions/1214496/how-to-get-environment-from-a-subprocess-in-python
#def validate_pair(ob):
#    try:
#        if not (len(ob) == 2):
#            print("Unexpected result:", ob, file = sys.stderr)
#            raise ValueError
#    except:
#        return False
#    return True

def consume(iterator):
    try:
        while True:
            next(iterator)
    except StopIteration:
        pass

def get(env_cmd, initial = None, arguments = None):
    """
    Take a command (either a single command or list of arguments)
    and return the environment created after running that command.
    Note that if the command must be a batch file or .cmd file, or the
    changes to the environment will not be captured.

    If initial is supplied, it is used as the initial environment passed
    to the child process.
    """
    if not os.path.lexists(env_cmd):
        raise Exception("Can not find {0} to get an environment from it.".format(env_cmd))

    #if not isinstance(env_cmd, (list, tuple)):
    #    env_cmd = [env_cmd]
    # construct the command that will alter the environment
    #env_cmd = subprocess.list2cmdline(env_cmd)

    # create a tag so we can tell in the output when the proc is done
    tag = 'Done running command'
    # construct a cmd.exe command to do accomplish this
    cmd = 'cmd.exe /s /c "\"{env_cmd}\" {arguments}&& echo "{tag}" && set"'.format(**vars())

    # launch the process
    proc = subprocess.Popen(cmd, stdout = subprocess.PIPE, env = initial)
    # parse the output sent to stdout
    lines = proc.stdout
    # consume whatever output occurs until the tag is reached
    consume(itertools.takewhile(lambda line: tag not in line, lines))
    # parse key/values into pairs
    pairs = (line.rstrip().split('=', 1) for line in lines)
    # make sure the pairs are valid
    valid_pairs = (pair for pair in pairs if len(pair) == 2)
    # construct a dictionary of the pairs
    result = dict(valid_pairs)
    # let the process finish
    proc.communicate()
    return result
