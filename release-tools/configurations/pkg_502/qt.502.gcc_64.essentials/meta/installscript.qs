/* This file is part of the Qt SDK

*/

// constructor
function Component()
{
}

Component.prototype.beginInstallation = function()
{
    installer.setValue(component.name + "_qtpath", "@TargetDir@" + "%TARGET_INSTALL_DIR%");
}

Component.prototype.createOperations = function()
{
    component.createOperations();

    if (installer.value("os") == "x11") {
        var qtPath = "@TargetDir@/%TARGET_INSTALL_DIR%";
        var qmakeBinary = "@TargetDir@/%TARGET_INSTALL_DIR%/bin/qmake";
        addInitQtPatchOperation(component, "linux", qtPath, qmakeBinary, "qt5");

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

        component.addOperation("Execute",
            new Array("{0}", "@SDKToolBinary@", "addQt", "--id", component.name, "--name", "Qt 5.0.2 GCC 64bit", "--type", "Qt4ProjectManager.QtVersion.Desktop", "--qmake", qmakeBinary));

        component.addOperation("Execute",
            new Array("{0}", "@SDKToolBinary@", "addKit", "--id", component.name + "_kit", "--name", "Desktop Qt 5.0.2 GCC 64bit", "--toolchain", "x86-linux-generic-elf-64bit", "--qt", component.name, "--debuggerengine", "1", "--devicetype", "Desktop"));

    }
}
