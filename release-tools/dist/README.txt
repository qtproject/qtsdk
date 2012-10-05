
Welcome to Qt!
==============

Qt is a cross-platform application and user interface framework. It
consists of a number of software libraries and development tools.

Qt is developed as an open source project. It is available under both
open source and commercial licenses.

All information on Qt is available on the Qt Developer Network:
http://qt-project.org

Be sure to check out the release notes, which will list any known
problems or limitations of this version:
http://qt-project.org/wiki/Category:Release


Understanding the Qt packages: Have you installed the right one?
----------------------------------------------------------------

The Qt source package ("qt-everywhere-opensource-src-<version>.xxx")
contains Qt in source code form. It is the right choice if you want to
build the framework and tools yourself.

The binary Qt packages ("qt-<operatingsystem>-opensource-<version>.xxx")
contain a binary distribution of Qt. It contains the the Qt libraries
and basic development tools, prebuilt for a certain platform
(operating system and compiler). The binary package also contains a
copy of the source package, as an optional install.

Note that the Qt packages do NOT contain Qt Creator, i.e. Qt's IDE
(Integrated Development Environment) application. If you are a
developer and you find yourself asking "How do I start Qt?", then you
should install Qt Creator, which comes in a separate package.

Finally, there are also the Qt SDK (Software Development Kit)
packages, which combine Qt Creator and a binary Qt distribution in a
single handy install.

The binary package is the right choice if you either
- Just need the Qt runtimes in order to run another application that
  needs them, or
- Want to try out some example programs built with Qt, or
- Intend to develop using a 3rd party IDE (e.g. MS Visual Studio), or
  just an editor and command line, in addition to Qt's basic
  development tools (Designer, Assistant, qmlscene, etc.), or
- Already have installed, or are planning to install Qt Creator


Directory structure
-------------------

The default top-level installation directory is the
directory "Qt-[version]" in your home directory.

The base directory of a particular binary distribution is something
similar to [installdir]/Desktop/Qt/[version]/[compiler]. This basedir
contains a number of subdirectories; "bin", "doc", "examples", etc.

The source code, if installed, can be found under [installdir]/Src.


Starting the development tools (binary package)
-----------------------------------------------

The directory [basedir]/bin contains all the Qt development
tools. Most are intended to be used from command line or an IDE, but
some may be launched as standalone applications. For example:
Assistant: The Qt documentation reader
qmlscene: Viewer for Qt Quick2 declarative QML applications
QMLViewer: Viewer for Qt Quick1 declarative QML applications
Designer: GUI designer for Qt widgets-based applications.


Running the example programs (binary package)
---------------------------------------------

Ready to run example programs can be found in [basedir]/examples. The
C++ based examples can be launched directly either from command line or
your file system browser.

The QML based Quick 2 examples are in [basedir]/examples/qtdeclarative. They
can be run with the qmlscene application (ref. above).

The QML based Quick 1 examples are in [basedir]/examples/qtquick1. They
can be run with the QMLViewer application (ref. above).


Building Qt from source
-----------------------

See [installdir]/Src/Qt/[version]/README and
http://qt-project.org/wiki/Building_Qt_5_from_Git
for instructions on building Qt from source.


Using it for developing software
--------------------------------

With Qt Creator, you can use this Qt version by selecting
Tools->Options->Build & Run->Add.., and point it to [basedir]/bin/qmake.

Otherwise, to compile C++ Qt applications, add [basedir]/include to
your build tool's search path for include files, and [basedir]/lib to
the search path for libraries.


Much more information is available at

http://qt-project.org/resources/getting_started
http://qt-project.org/doc/
http://qt-project.org


We hope you will enjoy using Qt!

- The Qt developers @ qt-project.org
