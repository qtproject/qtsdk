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

    if (installer.value("SDKToolBinary") == "")
        return;

    var qmakeBinary = "";
    if (installer.value("os") == "x11") {
        qmakeBinary = "@TargetDir@/%TARGET_INSTALL_DIR%/bin/qmake";
    }
    if (installer.value("os") == "win") {
        qmakeBinary = "@TargetDir@/%TARGET_INSTALL_DIR%/bin/qmake.exe";
    }

    // add Qt into QtCreator
    component.addOperation("Execute",
        new Array("{0}", "@SDKToolBinary@", "addQt", "--id", component.name, "--name", "Qt 5.1.0 for Android x86", "--type",
        "Qt4ProjectManager.QtVersion.Android", "--qmake", qmakeBinary));
    }
}
