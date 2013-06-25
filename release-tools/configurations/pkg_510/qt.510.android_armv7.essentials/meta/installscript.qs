/* This file is part of the Qt SDK

*/

// constructor
function Component()
{
    // add dynamic dependency for mingw48 TC for Android packages on Windows
    if (installer.value("os") == "win") {
        var mingw_tc_component = "qt.tools.win32_mingw48";
        if (installer.componentByName(mingw_tc_component) &&
            installer.componentByName(mingw_tc_component).installationRequested()) {
            component.addDependency(mingw_tc_component);
        }
    }
}

Component.prototype.beginInstallation = function()
{
    installer.setValue(component.name + "_qtpath", "@TargetDir@" + "%TARGET_INSTALL_DIR%");
}

Component.prototype.createOperations = function()
{
    component.createOperations();

    var qmakeBinary = "";
    var platform = "";
    if (installer.value("os") == "x11") {
        qmakeBinary = "@TargetDir@/%TARGET_INSTALL_DIR%/bin/qmake";
        platform = "linux";
    }
    if (installer.value("os") == "mac") {
        qmakeBinary = "@TargetDir@/%TARGET_INSTALL_DIR%/bin/qmake";
        platform = "mac";
    }
    if (installer.value("os") == "win") {
        qmakeBinary = "@TargetDir@/%TARGET_INSTALL_DIR%/bin/qmake.exe";
        platform = "windows";
    }

    var qtPath = "@TargetDir@/%TARGET_INSTALL_DIR%";
    addInitQtPatchOperation(component, platform, qtPath, qmakeBinary, "emb-arm");

    if (installer.value("SDKToolBinary") == "")
        return;

    // add Qt into QtCreator
    component.addOperation("Execute",
        new Array("{0}", "@SDKToolBinary@", "addQt", "--id", component.name, "--name", "Qt 5.1.0 for Android armv7", "--type",
        "Qt4ProjectManager.QtVersion.Android", "--qmake", qmakeBinary));
}
