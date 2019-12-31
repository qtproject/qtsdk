#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#############################################################################
##
## Copyright (C) 2020 The Qt Company Ltd.
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

import sys
import logging

LOG_FMT_CI = "%(asctime)s %(levelname)s:%(filename)s:%(lineno)d(%(process)d): %(message)s"
log = logging.getLogger("qtinstaller")
log.setLevel(logging.INFO)


# Unify format of all messages
try:
    from rainbow_logging_handler import RainbowLoggingHandler
    handler = RainbowLoggingHandler(sys.stderr, color_asctime=(None, None, False))
except ImportError:
    handler = logging.StreamHandler()

formatter = logging.Formatter(LOG_FMT_CI)
handler.setFormatter(formatter)
log.addHandler(handler)
