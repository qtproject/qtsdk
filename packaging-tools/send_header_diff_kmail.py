#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#############################################################################
#
# Copyright (C) 2022 The Qt Company Ltd.
# Contact: https://www.qt.io/licensing/
#
# This file is part of the qtqa module of the Qt Toolkit.
#
# $QT_BEGIN_LICENSE:BSD$
# Commercial License Usage
# Licensees holding valid commercial Qt licenses may use this file in
# accordance with the commercial license agreement provided with the
# Software or, alternatively, in accordance with the terms contained in
# a written agreement between you and The Qt Company. For licensing terms
# and conditions see https://www.qt.io/terms-conditions. For further
# information use the contact form at https://www.qt.io/contact-us.
#
# BSD License Usage
# Alternatively, you may use this file under the terms of the BSD license
# as follows:
#
# "Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#   * Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in
#     the documentation and/or other materials provided with the
#     distribution.
#   * Neither the name of The Qt Company Ltd nor the names of its
#     contributors may be used to endorse or promote products derived
#     from this software without specific prior written permission.
#
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."
#
# $QT_END_LICENSE$
#
#############################################################################

import argparse
import os
import sys
from subprocess import check_call


def send_headers(version, message_id, simulate):
    receiver = 'development@qt-project.org'
    subject = 'Qt ' + version + ' header diff: '
    print(f"Header diff: {subject}")

    for diff in os.listdir('.'):
        if diff.endswith('.diff'):
            print(f'Sending: {diff}')
            s = subject + diff
            h1 = 'In-Reply-To:<' + message_id + '>'
            h2 = 'References:<' + message_id + '>'
            args = ['kmail', '--subject', s, '--attach', diff, '--header', h1, '--header', h2, receiver]
            if simulate:
                print("Simulate:", " ".join(args))
            else:
                check_call(args)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="send_header_diff_kmail")

    parser.add_argument('--message', type=str, dest="message_id", required=True,
                        help='The original Message-ID (need to extract this from first mail sent, e.g. 2117407.DiL0mZzDaf@anton')
    parser.add_argument("--version", type=str, dest="version", required=True,
                        help="Version, for example 5.6.0")
    parser.add_argument("--simulate", dest="simulate", action="store_true",
                        help="Only print what would be done without creating the mails")

    args = parser.parse_args(sys.argv[1:])
    send_headers(version=args.version, message_id=args.message_id, simulate=args.simulate)
