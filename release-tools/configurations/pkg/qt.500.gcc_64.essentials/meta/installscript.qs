/* This file is part of the Qt SDK

*/

// constructor
function Component()
{
    if (component.fromOnlineRepository)
    {
        // Commented line below used by the packaging scripts
        //%IFW_DOWNLOADABLE_ARCHIVE_NAMES%
    }
}

Component.prototype.beginInstallation = function()
{
    installer.setValue(component.name + "_qtpath", "@TargetDir@" + "%TARGET_INSTALL_DIR%");
}

Component.prototype.createOperations = function()
{
    component.createOperations();

    if (installer.value("os") == "x11") {
        try {
            // patch Qt binaries
            var path = installer.value("TargetDir") + "%TARGET_INSTALL_DIR%";
            var script = path + "/patcher.sh";
            component.addOperation("Execute", "{0}", "/bin/bash", script, path);
            component.addOperation("Execute", "{0}", "/bin/rm", script);
        } catch( e ) {
            print( e );
        }

        if (installer.value("SDKToolBinary") == "")
            return;
        var qmakeBinary = "@TargetDir@/%TARGET_INSTALL_DIR%/bin/qmake";

        component.addOperation("Execute",
            new Array("{1}", "@SDKToolBinary@", "addQt", "--id", component.name, "--name", "Qt %QT_VERSION% GCC 64bit (SDK)", "--type", "Qt4ProjectManager.QtVersion.Desktop", "--qmake", qmakeBinary));

        component.addOperation("Execute",
            new Array("{1}", "@SDKToolBinary@", "addKit", "--id", component.name + "_kit", "--name", "Desktop Qt %QT_VERSION% GCC 64bit (SDK)", "--toolchain", "x86-linux-generic-elf-64bit", "--qt", component.name, "--debuggerengine", "1", "--devicetype", "Desktop"));

    }
}
