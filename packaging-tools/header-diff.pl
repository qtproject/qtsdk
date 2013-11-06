#!/usr/bin/perl
#############################################################################
##
## Copyright (C) 2013 Intel Corporation.
## Contact: http://www.qt-project.org/legal
##
## $QT_BEGIN_LICENSE:BSD$
## You may use this file under the terms of the BSD license as follows:
##
## "Redistribution and use in source and binary forms, with or without
## modification, are permitted provided that the following conditions are
## met:
##   * Redistributions of source code must retain the above copyright
##     notice, this list of conditions and the following disclaimer.
##   * Redistributions in binary form must reproduce the above copyright
##     notice, this list of conditions and the following disclaimer in
##     the documentation and/or other materials provided with the
##     distribution.
##   * Neither the name of Digia Plc and its Subsidiary(-ies) nor the names
##     of its contributors may be used to endorse or promote products derived
##     from this software without specific prior written permission.
##
##
## THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
## "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
## LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
## A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
## OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
## SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
## LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
## DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
## THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
## (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
## OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."
##
## $QT_END_LICENSE$
##
#############################################################################

use strict;
use warnings;

sub help {
    print "Usage: header-diff <revision-range> [srcdir] [builddir]\n" .
        "\n" .
        "revision-range          arguments to git diff, like v5.0.0..v5.1.0-rc1\n" .
        "srcdir                  the source qtsdk directory, "." if not provided\n" .
        "builddir                the build qtsdk directory, equal to srcdir if not provided\n";
    exit 0;
}

help() unless scalar @ARGV;
my $revrange = shift @ARGV;
my $srcdir = scalar @ARGV ? shift @ARGV : ".";
my $builddir = scalar @ARGV ? shift @ARGV : $srcdir;
my $includedir = "$builddir/qtbase/include";

my %module_list;

# Sanity check
die("Not a qtsdk source directory at $srcdir: no qtbase found")
    unless (-d "$srcdir/qtbase");
die("Not a qtsdk build directory at $builddir: no qtbase/include found")
    unless (-d $includedir);

my @modules_pro;
for my $repo (<$srcdir/*>) {
    next unless -d $repo && -d "$repo/src";
    push @modules_pro, <$repo/src/*/*.pro>;
}

PRO: for my $pro (@modules_pro) {
    #print "Processing .pro file $pro\n";
    open PRO, "<", $pro
        or die("Could not open $pro: $!");
    my $name;
    while (<PRO>) {
        next PRO if /TEMPLATE\s*=\s*subdir\b/;
        next unless /^\s*TARGET\s*=\s*(\w+)/;
        $name = $1;
        last;
    }
    close PRO;

    next unless defined $name;
    print "Found module $name in $pro\n";

    # Find the corresponding headers.pri
    unless (open HEADERS, "<", "$includedir/$name/headers.pri") {
        print " - No public headers for module $name\n";
        push @{$module_list{"no headers"}}, $name;
        next;
    }
    my @headers;
    while (<HEADERS>) {
        next unless /SYNCQT.HEADER_FILES\s*=\s*(.*)\s*/;
        @headers = split /\s+/, $1;
        last;
    }
    close HEADERS;

    # strip out headers outside the Git sources
    @headers = grep {!m,^\.\./,} @headers;

    unless (scalar @headers) {
        print " - No public headers for module $name\n";
        push @{$module_list{"no headers"}}, $name;
        next;
    }

    print " - Module has " . (scalar @headers) . " public headers now\n";

    open OUTPUT, ">", "$name.diff"
        or die("Could not open $name.diff for writing: $!");
    my $oldpwd = $ENV{PWD};
    $pro =~ s,/[^/]+$,,;
    chdir($pro) or die;

    # Get the git diff
    open DIFF, "-|", 'git', 'diff', '--diff-filter=M', '-w', '-b', $revrange, '--', @headers
        or die("Could not run git diff: $!");
    my $wrote_anything = 0;
    my $reading_header = 0;
    while (<DIFF>) {
        if (/^\@\@ -(\d+),(\d+) /) {
            # Ignore changes to the first 40 lines of a header
            # They're copyright changes
            $reading_header = $1 + $2 < 40;
        }
        next if $reading_header;
        $wrote_anything = 1;
        print OUTPUT $_;
    }

    chdir($oldpwd);
    close OUTPUT;
    close DIFF or unlink("$name.diff");
    if ($?) {
        print " - Git failed, skipping\n";
        push @{$module_list{"git failed"}}, $name;
    } elsif (!$wrote_anything) {
        print " - No changes!\n";
        push @{$module_list{"no changes"}}, $name;
    } else {
        print " - $name.diff created\n";
    }
}

print "\nResults";
print "\nModules with no public headers:\n\t";
print join("\n\t", sort @{$module_list{"no headers"}});
print "\nModules with no changes to public headers:\n\t";
print join("\n\t", sort @{$module_list{"no changes"}});
print "\nModules for which Git failed to retrieve changes:\n\t";
print join("\n\t", sort @{$module_list{"git failed"}});
print "\n";
