# Create the super cache so modules will add themselves to it.
cache(, super)

TEMPLATE      = subdirs

module_qtbase.subdir = qtbase
module_qtbase.target = module-qtbase

module_qtxmlpatterns.subdir = qtxmlpatterns
module_qtxmlpatterns.target = module-qtxmlpatterns
module_qtxmlpatterns.depends = module_qtbase

module_qtscript.subdir = qtscript
module_qtscript.target = module-qtscript
module_qtscript.depends = module_qtbase

module_qtjsbackend.subdir = qtjsbackend
module_qtjsbackend.target = module-qtjsbackend
module_qtjsbackend.depends = module_qtbase

module_qtdeclarative.subdir = qtdeclarative
module_qtdeclarative.target = module-qtdeclarative
module_qtdeclarative.depends = module_qtbase module_qtjsbackend

module_qtwebkit.file = qtwebkit/WebKit.pro
module_qtwebkit.depends = module_qtbase module_qtdeclarative
module_qtwebkit.target = module-qtwebkit

module_qttools.subdir = qttools
module_qttools.target = module-qttools
module_qttools.depends = module_qtbase

module_qtdoc.subdir = qtdoc
module_qtdoc.target = module-qtdoc
module_qtdoc.depends = module_qtbase module_qtdeclarative

module_qtquick1.subdir = qtquick1
module_qtquick1.target = module-qtquick1
module_qtquick1.depends = module_qtbase module_qtscript

module_qtcreator.file = qt-creator/qtcreator.pro
module_qtcreator.depends = module_qtbase module_qtquick1
module_qtcreator.target = module-qtcreator

# only qtbase is required to exist. The others may not - but it is the
# users responsibility to ensure that all needed dependencies exist, or
# it may not build.

SUBDIRS = module_qtbase

exists(qtxmlpatterns/qtxmlpatterns.pro) {
    SUBDIRS += module_qtxmlpatterns
    # These modules do not require qtxmlpatterns, but can use it if it is available
    module_qtdeclarative.depends += module_qtxmlpatterns
    module_qtquick1.depends += module_qtxmlpatterns
}

exists(qtjsbackend/qtjsbackend.pro): SUBDIRS += module_qtjsbackend
exists(qtdeclarative/qtdeclarative.pro) {
    SUBDIRS += module_qtdeclarative
    # These modules do not require qtdeclarative, but can use it if it is available
    module_qttools.depends += module_qtdeclarative
}
exists(qtscript/qtscript.pro): SUBDIRS += module_qtscript
exists(qtwebkit/WebKit.pro) {
    SUBDIRS +=  module_qtwebkit
    module_qttools.depends += module_qtwebkit
}
exists(qttools/qttools.pro) {
    SUBDIRS += module_qttools
    module_qtquick1.depends += module_qttools
}
exists(qtquick1/qtquick1.pro): SUBDIRS += module_qtquick1
exists(qtdoc/qtdoc.pro): SUBDIRS += module_qtdoc
exists(qt-creator/qtcreator.pro): SUBDIRS += module_qtcreator
