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
    try {
        var qtPath = "@TargetDir@/%TARGET_INSTALL_DIR%";
        var qmakeBinary = "@TargetDir@/%TARGET_INSTALL_DIR%/bin/qmake";
        addInitQtPatchOperation(component, "mac", qtPath, qmakeBinary, "qt5");

        if (installer.value("SDKToolBinary") == "")
            return;

        component.addOperation("Execute",
            new Array("{0}", "@SDKToolBinary@", "addQt", "--id", component.name, "--name", "Qt 5.1.1 clang 64bit", "--type", "Qt4ProjectManager.QtVersion.Desktop", "--qmake", qmakeBinary));

        component.addOperation("Execute",
            new Array("{0}", "@SDKToolBinary@", "addKit", "--id", component.name + "_kit", "--name", "Desktop Qt 5.1.1 clang 64bit", "--toolchain", "x86-macos-generic-mach_o-64bit", "--qt", component.name, "--debuggerengine", "1", "--devicetype", "Desktop"));
    } catch(e) {
        print(e);
    }
}
