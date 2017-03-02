# General

## Tools and Scripts

The following scripts are essential for building the Qt Installer Framework
(IFW):

* `bld_ifw_tools.py`
* `create_installer.py`
* `bld_qtcreator.py`
* `build_wrapper.py`

The scripts are available in `qtsdk.git`.

The `bld_ifw_tools.py` utility builds the static IFW libraries and tools.

The `create_installer.py` script creates offline installers, online installers,
and online repositories. It depends on the libraries and tools created by
`bld_ifw_tools.py`.

The `bld_qtcreator.py` script builds the Qt Creator core and the necessary
plugins. It depends on pre-built Qt packages.

The `build_wrapper.py` script wraps the above scripts into one and performs
the following tasks:

* Initializes the directory structure on the local network disk where the build
  artifacts are uploaded.
* Handles the actual builds (by calling the relevant scripts).
* Signs the macOS and Windows installers (if the signing keys and tools are
  correctly set up in the environment).
* Uploads build artifacts into correct places on the local or network disk.
* Triggers release test automation for installers (URL trigger).

## Build Environment Setup

* Python 2.7.10
* 7z (must be in the PATH)
* For network storage, direct SSH access should be enabled

## Generic Build Flow

The scripts and configuration files enable splitting the overall build flow into
separate steps. For example:

1. Build host Qt binaries.
2. Build Qt Creator and it's plugins (depends on build artifacts resulting from
   step 1).
3. Build IFW.
4. Build other content.

The above steps can be built more or less independently. Once the content
exists, we can:

1. Build an online repository for host Qt binaries (depends on steps 1 and 3).
2. Build an online repository for Qt Creator (depends on steps 2 and 3).
3. Build an online installer (depends on step 3).
4. Build an online repository for the maintenance tool (depends on step 3).
5. Build an online repository for other content.

The `build_wrapper.py` script handles most of the above-mentioned steps.
The command parameter (`-c`) specifies the step to execute. The required
environment for the script can be set as environment variables or loaded
from the `localbuild.ini` file.

### Building Content Versus Building Online Repositories

The online repository builds depend on having the actual content (that is,
*payload*) built first. Online repository builds use configuration files that
specify where to pick the content from. For example, from a network drive path.

## Generic Setup for Online Installers

Typically, you would use the following setup for creating online installers:

* Production online server that can handle high loads globally. Preferably, it
  should support HTTPS connections.
* Production online installer.
* Staging online server (for testing purposes).
* Test online installer.

# Qt Installer Framework

The Qt Installer Framework [http://doc.qt.io/qtinstallerframework/]
provides the tools to create online repositories as well as online and offline
installers.

Usually, IFW is built only once. The built libraries and tools are then re-used
each time an online repository or online installer is created. There is no need
to rebuild IFW every time the SDK or installer is updated.

Note that the IFW build itself does not result in an online installer. The main
results of the IFW build are:

* Tools to create online repositories, online installers, or offline installers.
* `installerbase`, which is the executable part of the online or offline
  installer and the maintenance tool.

The scripts take care of most of the steps, so you do not need to know all the
details. The important part is to understand that IFW is built once and then
re-used for the rest of the time.

## Building from Sources

Before the build, adjust the `[InstallerFramework.Build]` section in the
`localbuild.ini` file, as necessary.

Run the build script to build IFW completely from scratch, as follows:

`> python build_wrapper.py --pkg-conf-file=localbuild.ini -c ifw`

Once the build has completed successfully, the archived build contents are
copied to the following directories:

* `$HOME/build/opensource/ifw/2.0/`  
  By default, the branch name is used as destination directory name.
* `$HOME/build/opensource/ifw/<dest_dir_name>/`  
  If `IFW_REMOTE_RESULT_DEST_DIR_NAME` is set in `localbuild.ini`.

To change the IFW sources URI (Git URL or path to the source package) or the
used Qt version, edit the `[InstallerFramework.Build]` section in
`localbuild.ini`. To fine-tune the IFW build, you can edit `bld_ifw_tools.py`.

## Build Output

* `archivegen(.exe)`
* `binarycreator(.exe)`  
  Used to create the final online or offline installer executables.
* `devtool(.exe)`
* `installerbase(.exe)`  
  Used as the maintenance tool instance, online installer executable, or offline
  installer executable.
* `repogen(.exe)`  
  Used to create online repositories.

# Building Content

Before creating the online repositories, the content (payload) must be built.
The built content should be placed on a local or network drive in a structured
manner in .7z, .tar.gz, or .zip format.

The `build_wrapper.py` can be used to build Qt Creator and it's plugins.

## Building Qt

Qt CI is used to build Qt, and therefore `qtsdk.git` (`build_wrapper.py`) does
not contain scripts to build Qt anymore.

Example configure options used for Qt 5.8 are included. For more information,
see:

* `buildlog-qt58-Linux-RHEL_7_2-GCC-Linux-RHEL_7_2-X86_64.txt`
* `buildlog-qt58-MacOS-OSX_10_10-Clang-MacOS-OSX_10_10-X86_64.txt`
* `buildlog-qt58-Windows-Windows_10-MSVC2015-Windows-Windows_10-X86_64.txt`
* `buildlog-qt58-Windows-Windows_8_1-MSVC2013-Windows-Windows_8_1-X86.txt`

Qt CI builds the various Qt modules one by one. For each module, `make install`
is called and the resulting output is compressed into `.tar.gz` archives. These
archives are usually placed into persistent storage (such as a network drive).
The installer configuration files refer to these archives.

You can also make a monolithic build of Qt and refer to it from the installer
configuration files.

Note that to build Qt Creator using `build_wrapper.py`, pre-built Qt binaries
must exist on the local or network drive. The build scripts use the pre-built
binaries for faster Qt Creator builds.

## Building Qt Creator and Plugins

Before building, adjust the `[QtCreator.Build]` and `[QtCreator.Build.Plugin]`
sections in the `localbuild.ini` file, as necessary.

Run the `build_wrapper.py` script to build Qt Creator and the necessary plugins,
as follows:

`> python build_wrapper.py --pkg-conf-file=localbuild.ini -c build_creator`

When the building has completed successfully, the archived build contents are
copied to `$HOME/build/`.

## Locating Content on Disk

The online repository configuration files point to content on your local or
network disk. The scripts take as an argument the base path that is specified in
`localbuild.ini`. For example:
`http://mycompany.local.networkdrive/some/base/path/` or
`/home/<user>/mybuilds/`.

The configuration files specify the rest of the path for each file that is to be
included in online repository builds. For example,
`qtcreator/snapshots/4.1.1_57x/latest/linux_gcc_64_rhel66/qtcreator.7z` becomes
`/home/<user>/mybuilds/qtcreator/snapshots/4.1.1_57x/latest/linux_gcc_64_rhel66/qtcreator.7z`

# Building Online Repositories

## Repository Structure and Granularity

Before building online repositories, consider how to divide the content into
separate repositories. If all content is placed into one repository, the whole
repository is updated every time a single component within it is updated, and
therefore updates will become slower over time.

The repository structure could look as follows:

`https://mycompany.com/myonlinerepository/linux-x86_64/root`  
`https://mycompany.com/myonlinerepository/linux-x86_64/desktop/qtcreator`  
`https://mycompany.com/myonlinerepository/linux-x86_64/desktop/another_cool_tool`  
`https://mycompany.com/myonlinerepository/linux-x86_64/desktop/qt58`  
`https://mycompany.com/myonlinerepository/linux-x86_64/android/qt58`  
`https://mycompany.com/myonlinerepository/linux-x86_64/embeddedlinux/cool_embedded_tool`  
`https://mycompany.com/myonlinerepository/linux-x86_64/embeddedlinux/qt58`

It is also recommended that you set up a test server (staging area) where
repository build snapshots are uploaded for testing purposes. Once the content
of a repository has been tested, it can be pushed to production.

## Online Repository and Root Repository

To keep the online repository structure flexible, do not hard code all the
repository addresses into the online installer that is delivered to end users.
Instead, make the online installer point to a single repository. For example,
specify the following settings in the `config.xml` file:

`<RemoteRepositories>`  
    `<Repository>`  
        `<Url>https://mycompany.com/myonlinerepository/linux-x86_64/root</Url>`  
        `<Enabled>1</Enabled>`  
        `<DisplayName>MyCompany Linux-x64 root online repository</DisplayName>`  
    `</Repository>`  
`</RemoteRepositories>`

In the root repository
`https://mycompany.com/myonlinerepository/linux-x86_64/root/Updates.xml` file,
specify the following settings:

`<Updates>`  
`    <ApplicationName>{AnyApplication}</ApplicationName>`  
`    <ApplicationVersion>IFW_REPOSITORY_FORMAT_VERSION</ApplicationVersion>`  
`    <Checksum>true</Checksum>`  
`    <RepositoryUpdate>`  
`        <Repository action="add" url="https://mycompany.com/myonlinerepository/linux-x86_64/desktop/qtcreator" displayname="description..."/>`  
`        <Repository action="add" url="https://mycompany.com/myonlinerepository/linux-x86_64/desktop/another_cool_tool" displayname="description..."/>`  
`        <Repository action="add" url="https://mycompany.com/myonlinerepository/linux-x86_64/desktop/qt58" displayname="description..."/>`  
`        ...`  
`    </RepositoryUpdate>`  
`</Updates>`

Now you can make new repositories available to end users flexibly by adding a
new line into the root repository `Updates.xml`. Any `Updates.xml` can include
additional repositories using the same syntax.

**Note**

Once the end users have installed some components from the online repository,
a local dependency (maintenance tool) to remote repositories is established.
This means that you must:

* Never delete a repository from an online repository directly. Instead, specify
  the `<Repository action="remove" url="...">` setting in the root repository.
* Never change or patch the content (payload) in the online repository manually
  as that would result in a SHA1 checksum mismatch.
* Never push an update for a component in the online repository without
  increasing the version number of the component.

## Building an Online Repository

Example content from production:

`linux_x64/desktop/tools_qtcreator/Updates.xml`  
  `qt.tools.qtcreator/4.1.0-0meta.7z`  
  `qt.tools.qtcreator/4.1.0-0qtcreator.7z`  
  `qt.tools.qtcreator/4.1.0-0qtcreator.7z.sha1`

or

`windows_x86/desktop/tools_mingw/Updates.xml`  
  `qt.tools.win32_mingw48/...`  
  `qt.tools.win32_mingw482/4.8.2i686-4.8.2-release-posix-dwarf-rt_v3-rev3.7z`  
                          `4.8.2i686-4.8.2-release-posix-dwarf-rt_v3-rev3.7z.sha1`  
                          `4.8.2meta.7z`  
  `qt.tools.win32_mingw491/...`  
  `qt.tools.win32_mingw492/...`  
  `qt.tools.win32_mingw530/5.3.0-0i686-5.3.0-release-posix-dwarf-rt_v4-rev0.7z`  
                          `5.3.0-0i686-5.3.0-release-posix-dwarf-rt_v4-rev0.7z.sha1`  
                          `5.3.0-0meta.7z`

There are two main use cases for building online repositories:

* Creating a new repository that does not exist yet in production.
* Creating a repository to update an existing repository.

When you create an online repository that does not exist in production yet, you
can upload it as-is and include it in the root repository (as explained
earlier).

When you create a repository to update an existing repository, keep in mind that
the version number must be increased for the updated component inside the
`package.xml` so that the maintenance tool can promote the update to end users:

`<Version>1.2.3-45<Version> should become <Version>1.2.3-46<Version>`

### Replacing the Production Repository in Phases

`Updates.xml` contains mappings to payload archive names. Therefore, always make
sure that the payload is uploaded to production first. The version number is
prepended to archive names, and therefore the previous packages are not
overwritten. When the payload has been uploaded, replace the `Updates.xml` file
in production with the new version.

If the production system uses mirroring or caching of the files, you may need to
wait some hours before pushing the new `Updates.xml` to production. In some
systems, the cache expiry time can be set to zero for particular files, which in
this case would be for the `Updates.xml` files.

1. To build a network updated online repository locally or on a distributed
   build system member, in `localbuild.ini` set the `RELEASE_DESCRIPTION_FILE`
   to the file that defines your repository builds:  
   `> python build_wrapper.py -c repo_build --pkg-conf-file=localbuild.ini`

2. Update the repository.

## Maintenance Tool

The maintenance tool executable is produced as output of the IFW build, as
described in the *Qt Installer Framework* section.

The online repositories usually contain a maintenance tool component to provide
updates to your local maintenance tool instance. The maintenance tool component
online repository is just like any other component with the exception that it
updates itself.

### Offline Installer

At the end of a successful installation, the maintenance tool or uninstaller
executable in the installation root directory is extracted from the offline
installer itself.

### Online Installer

If a maintenance tool component is not included in online repositories, the
process is similar to that for the offline installer. No updates for the
maintenance tool executable are available.

If a maintenance tool component is included in online repositories, the
maintenance tool executable is installed from the online repositories. That is,
it is not extracted from the online installer executable.

Note that you should ensure that the maintenance tool in the production online
repository is always the latest revision to avoid using a newer online installer
(IFW build) than what would be installed with the maintenance tool. This could
cause issues depending on the changes in the used IFW revision.

For example, the maintenance tool online repository could look as follows:

`linux_x64/desktop/tools_maintenancetool/Updates.xml`  
                                        `mycompany.tools.maintenancetool/2.0.4-0meta.7z`  
                                        `mycompany.tools.maintenancetool/2.0.4-0maintenancetool.7z`  
                                        `mycompany.tools.maintenancetool/2.0.4-0maintenancetool.7z.sha1`  

## Pushing Online Repository Updates to Production

The process can vary greatly depending on the used production system. Typically,
the tasks should be completed in the following order:

1. Push data files.
2. Push Updates.xml.

### Pushing Data Files

For example, the following files could be pushed during a maintenance tool
repository update:

* `mycompany.tools.maintenancetool/2.0.4-0meta.7z`
* `mycompany.tools.maintenancetool/2.0.4-0maintenancetool.7z`
* `mycompany.tools.maintenancetool/2.0.4-0maintenancetool.7z.sha1`

Note that all data files are preprended with a version number (set in the
`<Version>` element in the package.xml file) so you can safely copy the
data files to the same directory where the current production versions of the
files are located. Therefore, it is important to ensure the version number is
increased for each component.

After this step, the directory could look something like:

* `mycompany.tools.maintenancetool/2.0.2-0meta.7z`
* `mycompany.tools.maintenancetool/2.0.2-0maintenancetool.7z`
* `mycompany.tools.maintenancetool/2.0.2-0maintenancetool.7z.sha1`
* `mycompany.tools.maintenancetool/2.0.3-0meta.7z`
* `mycompany.tools.maintenancetool/2.0.3-0maintenancetool.7z`
* `mycompany.tools.maintenancetool/2.0.3-0maintenancetool.7z.sha1`
* `mycompany.tools.maintenancetool/2.0.4-0meta.7z`
* `mycompany.tools.maintenancetool/2.0.4-0maintenancetool.7z`
* `mycompany.tools.maintenancetool/2.0.4-0maintenancetool.7z.sha1`

### Pushing Updates.xml

In this case, the original Updates.xml file needs to be overwritten.

If the production system uses mirroring, you must ensure that all the data
files that you pushed in previous step have been synchronized before updating
the Updates.xml file. When the users load the updated Updates.xml file, the data
files must be in sync as well.

If possible, one can set cache expiry time to zero for Updates.xml file to
reduce the sync delays.

**Note**

If you notice something got broken during the update process, do not revert to
previous file versions from backups. IFW does not support roll-back
functionality, and therefore the maintenance tool will not allow the users
to reinstall the previous version known to work.

The broken component needs to be fixed and a new version (with version number
increase) needs to be pushed to production first. The users need to uninstall
the broken component and install the fixed one.

# Configuration Files

This section describes how the IFW presents installable components to the users.
Consider the following installation tree structure that is visible in the
Qt opensource online installer:

`qt`  
  `57`  
    `msvc2013 32-bit`  
    `msvc2013 64-bit`  
    `...`  
    `Android x86`  
  `56`  
    `msvc2013 32-bit`  
    `msvc2013 64-bit`  
    `... `  
  `...`  
  `Tools`  
    `Qt Creator 4.1.0`  
    `MinGW 5.3.0`  
    `...`

This is a direct mapping of the components used to create the online repository
(or offline installer):

* `qt`
* `qt.57`
* `qt.57.win32_msvc2013`
* `qt.57.win32_msvc2013_64`
* `qt.57.android_x86`
* `qt.56`
* `qt.56.win32_msvc2013`
* `qt.56.win32_msvc2013_64`
* `qt.tools.qtcreator`
* `qt.tools.win32_mingw530`

For example, the component template for `qt.57.win32_msvc2013` shown above is
located in:
`packaging-tools/configurations/pkg_tools/pkg_58/qt.57.win32_msvc2013`.

This package template contains two files in a subdirectory:

* `meta/package.xml`
* `meta/installscript.qs`

The `package.xml` contains the `<DisplayName>` element which specifies the user
friendly string that is displayed to the users in the list of components in the
installer user interface.

All the package templates are located in
`packaging-tools/configurations/pkg_templates`. To include the selected package
template in the online repository or offline installer builds, specify it in the
configuration files.

The syntax is the following:

`[qt.57]`  
`# section details ...`

`[qt.57.win32_msvc2013]`  
`# section details ...`

`[qt.57.win32_msvc2013_64]`  
`# section details ...`

The above `example-configuration-conf` file would include the following
components in the online repository or offline installer build: `qt.57`,
`qt.57.win32_msvc2013`, and `qt.57.win32_msvc2013_64`.

A configuration file can include other configuration files , as necessary.
To see a good example, open the following file:
`packaging-tools/configurations/offline_installer_jobs/5.7/linux_x64`

`[PackageConfigurationFiles]`  
`file_list: qt-conf,`  
           `qt-license-conf,`  
           `qt-installer-changelog,`  
           `qt57-src-conf,`  
           `qt57-doc-examples-conf,`  
           `x86_64-qt57-gcc-conf,`  
           `x86_64-tools-qtcreator-qt57x-conf`

You can add granularity to how each configuration file includes the actual
installer components (package templates). For example, the
`x86_64-qt57-gcc-conf` file can be shared by the following configurations:

* `packaging-tools/configurations/offline_installer_jobs/5.7/linux_x64`
* `packaging-tools/configurations/repository_configs/desktop_qt5/linux_x64_repository_57`


Use the following syntax to specify components in a configuration file and to
map the payload it contains:

`[qt.57.gcc_64]`  
`archives:               foo_bar.qtbase,`  
                        `foo_bar.qtdeclarative,`  
                        `foo_bar.qtscript,`  
                        `foo_bar.something_else`  
`target_install_base:    /component_base_path_here/gcc_64`  
`[foo_bar.qtbase]`  
`archive_uri:            /my_network_drive_http_base_path/qtbase-Linux-RHEL_6_6-GCC-Linux-RHEL_6_6-X86_64.7z`  
`package_strip_dirs:     1`  
`target_install_dir:     /`  
`[foo_bar.qtdeclarative]`  
`archive_uri:            /my_network_drive_http_base_path/qtbase-Linux-RHEL_6_6-GCC-Linux-RHEL_6_6-X86_64.7z`  
`package_strip_dirs:     1`  
`target_install_dir:     /`  
`[foo_bar.qtscript]`  
`archive_uri:            /my_network_drive_http_base_path/qtbase-Linux-RHEL_6_6-GCC-Linux-RHEL_6_6-X86_64.7z`  
`package_strip_dirs:     1`  
`target_install_dir:     /`  
`[foo_bar.something_else]`  
`archive_uri:            http://master.qt.io/development_releases/prebuilt/icu/prebuilt/rhel65/icu_52_1_rhel_6_5_64.7z`  
`package_strip_dirs:     0`  
`target_install_dir:     /bin`

The above example would include one component in the installer build:
`qt.57.gcc_64`.

The rest of the elements specify the payload that the component contains. A
single component in the installer can collect payload archives from multiple
locations. The user enters the installation base directory in the installer user
interface. For example: `/home/user/johnsmith`.

* `archives` is a comma-separated list of the values specified in the following
  sections.
* `target_install_base` is appended to the `/home/user/johnsmith` path to form
  `home/user/johnsmith/component_base_path_here/gcc_64`. This is common base
  directory for all archives defined for the component.
* `archive_uri` specifies the location to fetch the payload archive from. It can
  be an absolute file system path or URL. By default, this path is appended to
  the package storage server base path to form a full URL. For example:
  `http://mycompany.intra/qtbuilds_base_path/` + `archive_uri`
* `package_strip_dirs` can be used  to strip away dirs if the payload `.7z`
  archive contains an unnecessary directory structure. For example, if the
  archive has the directory structure `/home/qtbuilder/build/<actual content>`
  and the value of `package_strip_dirs` is 3, then the scripts will repackage
  the archive so that the `.7z` contains only `<actual content>` at the root
  directory. Otherwise, the unnecessary directory structure would end up in the
  users' installation when installing the specific component.
* `target_install_dir` specifies further subdirectories for installing the
  archives. For example: `/home/user/johnsmith` + `target_install_base` +
  `target_install_dir`

# Concrete Example

1. Run the following script to build IFW:  
   `> python build_wrapper.py -c ifw --pkg-conf-file=localbuild.ini`
2. To build the online installer edit
   `packaging-tools/configurations/linux/config.xml.template.linux-x64.qt5-sdk`
   by changing the company name, icons, and other relevant elements, and by
   changing the URLs in the `<RemoteRepositories>` element.
3. Edit `packaging-tools/releases/onlineclient-simple`, if necessary.
4. Edit `localbuild.ini` to set the following value:  
   `RELEASE_DESCRIPTION_FILE=releases/onlineclient-simple`
5. Run the following script to build the online installer:  
   `> python build_wrapper.py -c online_installer --pkg-conf-file=localbuild.ini`
6. Edit `localbuild.ini` to set the following value:
   `RELEASE_DESCRIPTION_FILE=releases/maintenancetool`
7. Run the following script to build the maintenance tool online repository:  
   `> python build_wrapper.py -c repo_build --pkg-conf-file=localbuild.ini`
