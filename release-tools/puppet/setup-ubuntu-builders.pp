# Copyright (C) 2012 Nokia Corporation and/or its subsidiary(-ies).
# Contact: http://www.qt-project.org/
#
# You may use this file under the terms of the 3-clause BSD license.
# See the file LICENSE from this package for details.
#
# Usage: puppet apply setup-ubuntu-builders.pp

define user_homedir ($group, $fullname, $prefix = "/home", $ingroups = '') {
  user { "$name":
    ensure => present,
    comment => "$fullname",
    gid => "$group",
    groups => $ingroups,
    membership => minimum,
    shell => "/bin/bash",
    home => "$prefix/$name",
#    require => Group[$group],
  }

  exec { "$name homedir":
    command => "/bin/cp -R /etc/skel $prefix/$name; /bin/chown -R $name:$group $prefix/$name",
    creates => "$prefix/$name",
    require => User[$name],
  }

  exec { "$name ssh":
    command => "/bin/mkdir -p $prefix/$name/.ssh; /bin/chmod 700 $prefix/$name/.ssh; /bin/chown -R $name:$group $prefix/$name/.ssh",
    creates => "$prefix/$name/.ssh",
    require => Exec["$name homedir"],
  }
}

exec { '/bin/su jenkins -c "/usr/bin/ccache -M 10G"': }

user_homedir { "jenkins":
  prefix => "/var/lib",
  group => "nogroup",
  fullname => "Jenkins Remote Account",
}

file { "/opt/install/": ensure => "directory", owner => jenkins, group => "nogroup" }

ssh_authorized_key { 'jenkins':
  type => 'ssh-rsa',
  user => 'jenkins',
  require => Exec['jenkins ssh'],
  key => 'AAAAB3NzaC1yc2EAAAADAQABAAABAQDGCELBgrJ3CCQElGl0l4O7Sn40KVs1jBUWRX4WjFOir9jtAhM330U8NbQS4LfiN6kzZA/vjPtc0Sqgkuj8Mndfnvjabm1Q7SM79wfuQSMp+9d0YbojgrHs3Dk9GCVWKS0tgLLc7ouWfFm13LVSZWtJ1geTwgy2+0xxUxvMMxkbyvY1j/BWZC3nf4h2d+APMABOr++ku4RVu6GqhHr4gIs6XEFUgXJn+Ary5ksUviGVHhMV+mXlfI7abHXoru3dnHm4LCjUYtqPvd7U9TUvo16NJVG/JwI6CNMx5WFwHkAx8SIscMWAeDQpKTQ4MMbx/p0xUIXEXO8PbOakr0RUMEmF'
}

#file { '/srv/build_storage': owner => 'root', group => 'root', ensure => 'directory' }

# General
package { 'git-core': ensure => installed }
package { 'ccache': ensure => installed }
package { 'openjdk-6-jre': ensure => installed }
package { 'p7zip-full': ensure => installed }
package { 'zip': ensure => installed }
package { 'chrpath': ensure => installed }
package { 'gdb': ensure => installed }
package { 'python-software-properties': ensure => installed }
package { 'python2.7': ensure => installed }

# Gdb/Python
package { 'texi2html': ensure => installed }
package { 'texinfo': ensure => installed }

# Qt
package { 'debhelper': ensure => installed }
package { 'flex': ensure => installed }
package { 'freetds-dev': ensure => installed }
package { 'libasound2-dev': ensure => installed }
package { 'libaudio-dev': ensure => installed }
package { 'libcups2-dev': ensure => installed }
package { 'libdbus-1-dev': ensure => installed }
package { 'libfreetype6-dev': ensure => installed }
package { 'libgl1-mesa-dev': ensure => installed }
package { 'libglib2.0-dev': ensure => installed }
package { 'libglu-dev': ensure => installed }
package { 'libglu1-mesa-dev': ensure => installed }
package { 'libgstreamer-plugins-base0.10-dev': ensure => installed }
package { 'libgstreamer0.10-dev': ensure => installed }
package { 'libgtk2.0-dev': ensure => installed }
package { 'libice-dev': ensure => installed }
package { 'libjpeg-dev': ensure => installed }
package { 'libmng-dev': ensure => installed }
package { 'libmysqlclient-dev': ensure => installed }
package { 'libpam0g-dev': ensure => installed }
package { 'libpng12-dev': ensure => installed }
package { 'libpq-dev': ensure => installed }
package { 'libreadline-dev': ensure => installed }
package { 'libsm-dev': ensure => installed }
package { 'libsqlite0-dev': ensure => installed }
package { 'libsqlite3-dev': ensure => installed }
package { 'libtiff4-dev': ensure => installed }
package { 'libx11-dev': ensure => installed }
package { 'libxcursor-dev': ensure => installed }
package { 'libxext-dev': ensure => installed }
package { 'libxft-dev': ensure => installed }
package { 'libxi-dev': ensure => installed }
package { 'libxinerama-dev': ensure => installed }
package { 'libxmu-dev': ensure => installed }
package { 'libxrandr-dev': ensure => installed }
package { 'libxrender-dev': ensure => installed }
package { 'libxslt1-dev': ensure => installed }
package { 'libxt-dev': ensure => installed }
package { 'libxtst-dev': ensure => installed }
package { 'libxv-dev': ensure => installed }
package { 'pkg-kde-tools': ensure => installed }
package { 'quilt': ensure => installed }
package { 'sharutils': ensure => installed }
package { 'unixodbc-dev': ensure => installed }
package { 'zlib1g-dev': ensure => installed }
package { 'gtk-doc-tools': ensure => installed }
# WebKit 2 deps
package { 'libicu-dev': ensure => installed }
package { 'bison': ensure => installed }
package { 'gperf': ensure => installed }

case $::operatingsystemrelease {
  '10.04': {
     # Compat packages from PPAs
     exec { 'py26alt': command => '/usr/sbin/update-alternatives --install /usr/bin/python python /usr/bin/python2.6 10' }
     exec { 'py27alt': command => '/usr/sbin/update-alternatives --install /usr/bin/python python /usr/bin/python2.7 1' }
     exec { 'pickpydefault':
       command => '/usr/sbin/update-alternatives --set python /usr/bin/python2.7',
       require => [ Exec['py26alt'], Exec['py27alt'] ]
     }
     exec { '/usr/bin/apt-add-repository ppa:pythoneers/lts':
       require => Package['python-software-properties'],
       creates => "/etc/apt/sources.list.d/pythoneers-lts-lucid.list"
     }
     package { 'libxcb-atom1': ensure => installed }
     package { 'libxcb-atom1-dev': ensure => installed }
     package { 'libxcb-aux0': ensure => installed }
     package { 'libxcb-aux0-dev': ensure => installed }
     package { 'libxcb-composite0': ensure => installed }
     package { 'libxcb-composite0-dbg': ensure => installed }
     package { 'libxcb-composite0-dev': ensure => installed }
     package { 'libxcb-damage0': ensure => installed }
     package { 'libxcb-damage0-dbg': ensure => installed }
     package { 'libxcb-damage0-dev': ensure => installed }
     package { 'libxcb-dpms0': ensure => installed }
     package { 'libxcb-dpms0-dbg': ensure => installed }
     package { 'libxcb-dpms0-dev': ensure => installed }
     package { 'libxcb-dri2-0': ensure => installed }
     package { 'libxcb-dri2-0-dbg': ensure => installed }
     package { 'libxcb-dri2-0-dev': ensure => installed }
     package { 'libxcb-event1': ensure => installed }
     package { 'libxcb-event1-dev': ensure => installed }
     package { 'libxcb-glx0': ensure => installed }
     package { 'libxcb-glx0-dbg': ensure => installed }
     package { 'libxcb-glx0-dev': ensure => installed }
     package { 'libxcb-icccm1': ensure => installed }
     package { 'libxcb-icccm1-dev': ensure => installed }
     package { 'libxcb-image0': ensure => installed }
     package { 'libxcb-image0-dev': ensure => installed }
     package { 'libxcb-keysyms1': ensure => installed }
     package { 'libxcb-keysyms1-dev': ensure => installed }
     package { 'libxcb-property1': ensure => installed }
     package { 'libxcb-property1-dev': ensure => installed }
     package { 'libxcb-randr0': ensure => installed }
     package { 'libxcb-randr0-dbg': ensure => installed }
     package { 'libxcb-randr0-dev': ensure => installed }
     package { 'libxcb-record0': ensure => installed }
     package { 'libxcb-record0-dbg': ensure => installed }
     package { 'libxcb-record0-dev': ensure => installed }
     package { 'libxcb-render-util0': ensure => installed }
     package { 'libxcb-render-util0-dev': ensure => installed }
     package { 'libxcb-render0': ensure => installed }
     package { 'libxcb-render0-dbg': ensure => installed }
     package { 'libxcb-render0-dev': ensure => installed }
     package { 'libxcb-reply1': ensure => installed }
     package { 'libxcb-reply1-dev': ensure => installed }
     package { 'libxcb-res0': ensure => installed }
     package { 'libxcb-res0-dbg': ensure => installed }
     package { 'libxcb-res0-dev': ensure => installed }
     package { 'libxcb-screensaver0': ensure => installed }
     package { 'libxcb-screensaver0-dbg': ensure => installed }
     package { 'libxcb-screensaver0-dev': ensure => installed }
     package { 'libxcb-shape0': ensure => installed }
     package { 'libxcb-shape0-dbg': ensure => installed }
     package { 'libxcb-shape0-dev': ensure => installed }
     package { 'libxcb-shm0': ensure => installed }
     package { 'libxcb-shm0-dbg': ensure => installed }
     package { 'libxcb-shm0-dev': ensure => installed }
     package { 'libxcb-sync0': ensure => installed }
     package { 'libxcb-sync0-dbg': ensure => installed }
     package { 'libxcb-sync0-dev': ensure => installed }
     package { 'libxcb-xevie0': ensure => installed }
     package { 'libxcb-xevie0-dbg': ensure => installed }
     package { 'libxcb-xevie0-dev': ensure => installed }
     package { 'libxcb-xf86dri0': ensure => installed }
     package { 'libxcb-xf86dri0-dbg': ensure => installed }
     package { 'libxcb-xf86dri0-dev': ensure => installed }
     package { 'libxcb-xfixes0': ensure => installed }
     package { 'libxcb-xfixes0-dbg': ensure => installed }
     package { 'libxcb-xfixes0-dev': ensure => installed }
     package { 'libxcb-xinerama0': ensure => installed }
     package { 'libxcb-xinerama0-dbg': ensure => installed }
     package { 'libxcb-xinerama0-dev': ensure => installed }
     package { 'libxcb-xprint0': ensure => installed }
     package { 'libxcb-xprint0-dbg': ensure => installed }
     package { 'libxcb-xprint0-dev': ensure => installed }
     package { 'libxcb-xtest0': ensure => installed }
     package { 'libxcb-xtest0-dbg': ensure => installed }
     package { 'libxcb-xtest0-dev': ensure => installed }
     package { 'libxcb-xv0': ensure => installed }
     package { 'libxcb-xv0-dbg': ensure => installed }
     package { 'libxcb-xv0-dev': ensure => installed }
     package { 'libxcb-xvmc0': ensure => installed }
     package { 'libxcb-xvmc0-dbg': ensure => installed }
     package { 'libxcb-xvmc0-dev': ensure => installed }
     package { 'libxcb1': ensure => installed }
     package { 'libxcb1-dbg': ensure => installed }
     package { 'libxcb1-dev': ensure => installed }
   }
   '11.10': {
     # Qt 5 deps
     package { 'libxcb-composite0': ensure => installed }
     package { 'libxcb-composite0-dbg': ensure => installed }
     package { 'libxcb-composite0-dev': ensure => installed }
     package { 'libxcb-damage0': ensure => installed }
     package { 'libxcb-damage0-dbg': ensure => installed }
     package { 'libxcb-damage0-dev': ensure => installed }
     package { 'libxcb-doc': ensure => installed }
     package { 'libxcb-dpms0': ensure => installed }
     package { 'libxcb-dpms0-dbg': ensure => installed }
     package { 'libxcb-dpms0-dev': ensure => installed }
     package { 'libxcb-dri2-0': ensure => installed }
     package { 'libxcb-dri2-0-dbg': ensure => installed }
     package { 'libxcb-dri2-0-dev': ensure => installed }
     package { 'libxcb-ewmh1': ensure => installed }
     package { 'libxcb-ewmh1-dev': ensure => installed }
     package { 'libxcb-glx0': ensure => installed }
     package { 'libxcb-glx0-dbg': ensure => installed }
     package { 'libxcb-glx0-dev': ensure => installed }
     package { 'libxcb-icccm4': ensure => installed }
     package { 'libxcb-icccm4-dev': ensure => installed }
     package { 'libxcb-randr0': ensure => installed }
     package { 'libxcb-randr0-dbg': ensure => installed }
     package { 'libxcb-randr0-dev': ensure => installed }
     package { 'libxcb-record0': ensure => installed }
     package { 'libxcb-record0-dbg': ensure => installed }
     package { 'libxcb-record0-dev': ensure => installed }
     package { 'libxcb-render0': ensure => installed }
     package { 'libxcb-render0-dbg': ensure => installed }
     package { 'libxcb-render0-dev': ensure => installed }
     package { 'libxcb-res0': ensure => installed }
     package { 'libxcb-res0-dbg': ensure => installed }
     package { 'libxcb-res0-dev': ensure => installed }
     package { 'libxcb-screensaver0': ensure => installed }
     package { 'libxcb-screensaver0-dbg': ensure => installed }
     package { 'libxcb-screensaver0-dev': ensure => installed }
     package { 'libxcb-shape0': ensure => installed }
     package { 'libxcb-shape0-dbg': ensure => installed }
     package { 'libxcb-shape0-dev': ensure => installed }
     package { 'libxcb-shm0': ensure => installed }
     package { 'libxcb-shm0-dbg': ensure => installed }
     package { 'libxcb-shm0-dev': ensure => installed }
     package { 'libxcb-sync0': ensure => installed }
     package { 'libxcb-sync0-dbg': ensure => installed }
     package { 'libxcb-sync0-dev': ensure => installed }
     package { 'libxcb-util0': ensure => installed }
     package { 'libxcb-util0-dev': ensure => installed }
     package { 'libxcb-xevie0': ensure => installed }
     package { 'libxcb-xevie0-dbg': ensure => installed }
     package { 'libxcb-xevie0-dev': ensure => installed }
     package { 'libxcb-xf86dri0': ensure => installed }
     package { 'libxcb-xf86dri0-dbg': ensure => installed }
     package { 'libxcb-xf86dri0-dev': ensure => installed }
     package { 'libxcb-xfixes0': ensure => installed }
     package { 'libxcb-xfixes0-dbg': ensure => installed }
     package { 'libxcb-xfixes0-dev': ensure => installed }
     package { 'libxcb-xinerama0': ensure => installed }
     package { 'libxcb-xinerama0-dbg': ensure => installed }
     package { 'libxcb-xinerama0-dev': ensure => installed }
     package { 'libxcb-xprint0': ensure => installed }
     package { 'libxcb-xprint0-dbg': ensure => installed }
     package { 'libxcb-xprint0-dev': ensure => installed }
     package { 'libxcb-xtest0': ensure => installed }
     package { 'libxcb-xtest0-dbg': ensure => installed }
     package { 'libxcb-xtest0-dev': ensure => installed }
     package { 'libxcb-xv0': ensure => installed }
     package { 'libxcb-xv0-dbg': ensure => installed }
     package { 'libxcb-xv0-dev': ensure => installed }
     package { 'libxcb-xvmc0': ensure => installed }
     package { 'libxcb-xvmc0-dbg': ensure => installed }
     package { 'libxcb-xvmc0-dev': ensure => installed }
     package { 'libxcb1': ensure => installed }
     package { 'libxcb1-dbg': ensure => installed }
     package { 'libxcb1-dev': ensure => installed }
     package { 'libxcb-image0': ensure => installed }
     package { 'libxcb-image0-dev': ensure => installed }
     package { 'libxcb-keysyms1': ensure => installed }
     package { 'libxcb-keysyms1-dev': ensure => installed }
     package { 'libxcb-render-util0': ensure => installed }
     package { 'libxcb-render-util0-dev': ensure => installed }
     package { 'libx11-xcb-dev': ensure => installed }
     # Qt 5 JsonDb deps
     package { 'libedit-dev': ensure => installed }
  }
  '12.04': {
     # Qt 5 deps
     package { 'libxcb-composite0': ensure => installed }
     package { 'libxcb-composite0-dbg': ensure => installed }
     package { 'libxcb-composite0-dev': ensure => installed }
     package { 'libxcb-damage0': ensure => installed }
     package { 'libxcb-damage0-dbg': ensure => installed }
     package { 'libxcb-damage0-dev': ensure => installed }
     package { 'libxcb-doc': ensure => installed }
     package { 'libxcb-dpms0': ensure => installed }
     package { 'libxcb-dpms0-dbg': ensure => installed }
     package { 'libxcb-dpms0-dev': ensure => installed }
     package { 'libxcb-dri2-0': ensure => installed }
     package { 'libxcb-dri2-0-dbg': ensure => installed }
     package { 'libxcb-dri2-0-dev': ensure => installed }
     package { 'libxcb-ewmh1': ensure => installed }
     package { 'libxcb-ewmh1-dev': ensure => installed }
     package { 'libxcb-glx0': ensure => installed }
     package { 'libxcb-glx0-dbg': ensure => installed }
     package { 'libxcb-glx0-dev': ensure => installed }
     package { 'libxcb-icccm4': ensure => installed }
     package { 'libxcb-icccm4-dev': ensure => installed }
     package { 'libxcb-randr0': ensure => installed }
     package { 'libxcb-randr0-dbg': ensure => installed }
     package { 'libxcb-randr0-dev': ensure => installed }
     package { 'libxcb-record0': ensure => installed }
     package { 'libxcb-record0-dbg': ensure => installed }
     package { 'libxcb-record0-dev': ensure => installed }
     package { 'libxcb-render0': ensure => installed }
     package { 'libxcb-render0-dbg': ensure => installed }
     package { 'libxcb-render0-dev': ensure => installed }
     package { 'libxcb-res0': ensure => installed }
     package { 'libxcb-res0-dbg': ensure => installed }
     package { 'libxcb-res0-dev': ensure => installed }
     package { 'libxcb-screensaver0': ensure => installed }
     package { 'libxcb-screensaver0-dbg': ensure => installed }
     package { 'libxcb-screensaver0-dev': ensure => installed }
     package { 'libxcb-shape0': ensure => installed }
     package { 'libxcb-shape0-dbg': ensure => installed }
     package { 'libxcb-shape0-dev': ensure => installed }
     package { 'libxcb-shm0': ensure => installed }
     package { 'libxcb-shm0-dbg': ensure => installed }
     package { 'libxcb-shm0-dev': ensure => installed }
     package { 'libxcb-sync0': ensure => installed }
     package { 'libxcb-sync0-dbg': ensure => installed }
     package { 'libxcb-sync0-dev': ensure => installed }
     package { 'libxcb-util0': ensure => installed }
     package { 'libxcb-util0-dev': ensure => installed }
     package { 'libxcb-xevie0': ensure => installed }
     package { 'libxcb-xevie0-dbg': ensure => installed }
     package { 'libxcb-xevie0-dev': ensure => installed }
     package { 'libxcb-xf86dri0': ensure => installed }
     package { 'libxcb-xf86dri0-dbg': ensure => installed }
     package { 'libxcb-xf86dri0-dev': ensure => installed }
     package { 'libxcb-xfixes0': ensure => installed }
     package { 'libxcb-xfixes0-dbg': ensure => installed }
     package { 'libxcb-xfixes0-dev': ensure => installed }
     package { 'libxcb-xinerama0': ensure => installed }
     package { 'libxcb-xinerama0-dbg': ensure => installed }
     package { 'libxcb-xinerama0-dev': ensure => installed }
     package { 'libxcb-xprint0': ensure => installed }
     package { 'libxcb-xprint0-dbg': ensure => installed }
     package { 'libxcb-xprint0-dev': ensure => installed }
     package { 'libxcb-xtest0': ensure => installed }
     package { 'libxcb-xtest0-dbg': ensure => installed }
     package { 'libxcb-xtest0-dev': ensure => installed }
     package { 'libxcb-xv0': ensure => installed }
     package { 'libxcb-xv0-dbg': ensure => installed }
     package { 'libxcb-xv0-dev': ensure => installed }
     package { 'libxcb-xvmc0': ensure => installed }
     package { 'libxcb-xvmc0-dbg': ensure => installed }
     package { 'libxcb-xvmc0-dev': ensure => installed }
     package { 'libxcb1': ensure => installed }
     package { 'libxcb1-dbg': ensure => installed }
     package { 'libxcb1-dev': ensure => installed }
     package { 'libxcb-image0': ensure => installed }
     package { 'libxcb-image0-dev': ensure => installed }
     package { 'libxcb-keysyms1': ensure => installed }
     package { 'libxcb-keysyms1-dev': ensure => installed }
     package { 'libxcb-render-util0': ensure => installed }
     package { 'libxcb-render-util0-dev': ensure => installed }
     package { 'libx11-xcb-dev': ensure => installed }
     # Qt 5 JsonDb deps
     package { 'libedit-dev': ensure => installed }
  }
}


