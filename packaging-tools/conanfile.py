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

from conans import ConanFile, CMake, tools, AutoToolsBuildEnvironment
import os


class HelloConan(ConanFile):
    name = "Hello"
    version = "0.2"
    user = ""
    channel = ""
    license = "<Put the package license here>"
    author = "<Put your name here> <And your email here>"
    url = "<Package recipe repository url here, for issues about the package>"
    description = "<Description of Hello here>"
    homepage = ""
    topics = ("<Put some tag here>", "<here>", "<and here>")
    settings = "os", "compiler", "build_type", "arch"
    options = {"shared": [True, False]}
    default_options = {"shared": False}
    generators = "cmake"
    # these files shouldn’t be used by the conanfile.py Python code, but to compile the library or generate the final package
    # these files will only be retrieved if requested binaries are not available or the user forces Conan to compile from sources
    exports_sources = "src/*", "!conanfile.py"
    requires = ""
    # requirements that are only installed and used when the package is built from sources
    build_requires = ""
    # declares the set of files that should be exported and stored side by side with the conanfile.py file to make the recipe work,
    # other python files that the recipe will import, some text file with data to read
    exports = ""

    # The folder in which the source code lives.
    # Defaulted to the conanfile's directory. A relative path to current directory can also be specified
    #source_folder = ""

    # Creates a unique ID for the package. Default package ID is calculated using settings, options and requires properties.
    # When a package creator specifies the values for any of those properties,
    # it is telling that any value change will require a different binary package.
    def package_id(self):
        # for example, to have only one binary package for several different compiler versions
        v = Version(str(self.settings.compiler.version))
        if self.settings.compiler == "gcc" and (v >= "4.5" and v < "5.0"):
            self.info.settings.compiler.version = "GCC 4 between 4.5 and 5.0"

    # Method used to retrieve the source code from any other external origin like github using $ git clone or just a regular download.
    def source(self):
        pass


    # Copy binaries from dependencies that might be necessary for the build() method to work.
    # After build() finishes, those copied (imported) files are removed, so they are not later unnecessarily repackaged.
    # This behavior can be avoided declaring the keep_imports=True attribute
    def imports(self):
        #self.copy("*.dll", "", "bin")
        #self.copy("*.dylib", "", "lib")

    def configure(self):
        if self.settings.os != "Windows":
            raise ConanInvalidConfiguration("Library MyLib is only supported for Windows")

    def requirements(self):
        # handle e.g. conditional dependencies
        if self.options.myoption:
            self.requires("zlib/1.2@drl/testing")
        else:
            self.requires("opencv/2.2@drl/stable")

    # Requirements that are only installed and used when the package is built from sources.
    # If there is an existing pre-compiled binary, then the build requirements for this package will not be retrieved
    def build_requirements(self):
        if self.settings.os == "Windows":
            self.build_requires("ToolWin/0.1@user/stable")

    def system_requirements(self):
        pack_name = None
        if os_info.linux_distro == "ubuntu":
            if os_info.os_version > "12":
                pack_name = "package_name_in_ubuntu_10"
            else:
                pack_name = "package_name_in_ubuntu_12"
        elif os_info.linux_distro == "fedora" or os_info.linux_distro == "centos":
            pack_name = "package_name_in_fedora_and_centos"
        elif os_info.is_macos:
            pack_name = "package_name_in_macos"
        elif os_info.is_freebsd:
            pack_name = "package_name_in_freebsd"
        elif os_info.is_solaris:
            pack_name = "package_name_in_solaris"

        if pack_name:
            installer = SystemPackageTool()
            installer.install(pack_name)  # Install the package, will update the package database

    # Used to configure or constraint the available options in a package, before they are given a value.
    # This will be executed before the actual assignment of options (then, such options values cannot be used inside this function).
    def config_options(self):
        pass

    def build(self):
        currentDir = os.getcwd()
        try:
            os.chdir("src")
            self.run('qmake')
            self.run('make -j8')
        except Exception as e:
            print("Error: %s", str(e))
            raise
        finally:
            os.chdir(currentDir)


        # OR

        cmake = CMake(self)
        cmake.configure(source_folder="src")
        cmake.build()

        # Explicit way:
        # self.run('cmake %s/hello %s'
        #          % (self.source_folder, cmake.command_line))
        # self.run("cmake --build . %s" % cmake.build_config)


        # Tips:

        # deps is a list of package names: ["Poco", "zlib", "OpenSSL"]
        deps = self.deps_cpp_info.deps

        # Get the sharedlinkflags property from OpenSSL package
        self.deps_cpp_info["OpenSSL"].sharedlinkflags

        # Get the SOMEVAR environment variable declared in the "package1"
        self.deps_env_info["package1"].SOMEVAR
        # Access to the environment variables globally
        os.environ["SOMEVAR"]

        # You can access the declared user_info.XXX variables of the requirements through the self.deps_user_info object like this
        self.deps_user_info["package1"].SOMEVAR



    # Using the self.copy() method, artifacts are copied from the build folder to the package folder.
    def package(self):

        # Tip:

        # This attribute is a dictionary with the keys and values provided in a conandata.yml
        # The file is automatically exported with the recipe.
        # This file can be used, for example, to declare a list of sources links and checksums for the recipe or a list patches to apply to them
        #self.conandata  #

        self.copy("*.h", dst="include", src="src")
        self.copy("*.lib", dst="lib", keep_path=False)
        self.copy("*.dll", dst="bin", keep_path=False)
        self.copy("*.dylib*", dst="lib", keep_path=False)
        self.copy("*.so", dst="lib", keep_path=False)
        self.copy("*.a", dst="lib", keep_path=False)

    # Each package has to specify certain build information for its consumers
    def package_info(self):
        self.cpp_info.name = "<PKG_NAME>"  # Alternative name for the package used by generators to create files or variables. Defaulted to the package name.
        self.cpp_info.includedirs = ["include"]  # Ordered list with include paths.
        self.cpp_info.libs = ["hello"]  # Ordered list of libs the client should link against, it is common that different configurations produce different library names
        self.cpp_info.libdirs = ["lib"]  # List of relative paths (starting from the package root) of directories in which to find library object binaries (*.lib, *.a, *.so, *.dylib)
        self.cpp_info.resdirs = ["res"]  # Directories where resources, data, etc can be found
        self.cpp_info.bindirs = ["bin"]  # Directories where executables and shared libs can be found
        self.cpp_info.srcdirs = []  # Directories where sources can be found. It might be used to store sources (for later debugging of packages, or to reuse those sources building them in other packages too)
        self.cpp_info.build_modules = []  # List of relative paths to build system related utility module files created by the package
        self.cpp_info.builddirs = [""]  # Ordered list with build scripts directory paths
        self.cpp_info.defines = []  # Pre-processor defines. It is common that the consumers have to specify some sort of defines in some cases, so that including the library headers matches the binaries.
        self.cpp_info.cflags = []  # Pure C flags. List of flags that the consumer should activate for proper behavior
        self.cpp_info.cxxflags = []  # C++ compilation flags. List of flags that the consumer should activate for proper behavior
        self.cpp_info.sharedlinkflags = []  # Linker flags. List of flags that the consumer should activate for proper behavior
        self.cpp_info.exelinkflags = []  # Linker flags. List of flags that the consumer should activate for proper behavior
        self.cpp_info.system_libs = []  # Ordered list of system libs the consumer should link against
        self.cpp_info.frameworks = []  # Ordered list with the framework names (OSX)
        self.cpp_info.frameworkdirs = ["Frameworks"]  # Ordered list with frameworks search paths (OSX)
        self.cpp_info.rootpath = ""  # Filled with the root directory of the package, see deps_cpp_info

        # Each package can also define some environment variables that the package needs to be reused
        # useful for "installer packages", to set the path with the “bin” folder of the packaged application

        # One of the most typical usages for the PATH environment variable, would be to add the current binary package directories to the path, so consumers can use those executables easily
        # assuming the binaries are in the "bin" subfolder
        self.env_info.PATH.append(os.path.join(self.package_folder, "bin"))
        self.env_info.othervar.append("OTHER VALUE")

        # The self.user_info object can be filled with any custom variable to be accessed in the packages reusing the recipe.
        self.user_info.FOO = "FOO"

    # This method can be used in a conanfile.py to install in the system or user folder artifacts from packages.
    # The deploy() method is designed to work on a package that is installed directly from its reference, as:
    #   $ conan install Pkg/0.1@user/channel
    #   ! All other packages and dependencies, even transitive dependencies of “Pkg/0.1@user/testing” will not be deployed,
    #     it is the responsibility of the installed package to deploy what it needs from its dependencies.
    def deploy(self):
        self.copy("*.exe")  # copy from current package
        self.copy_deps("*.dll")  # copy from dependencies

