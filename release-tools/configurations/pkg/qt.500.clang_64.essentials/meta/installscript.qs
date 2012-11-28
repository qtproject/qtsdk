/* This file is part of the Qt SDK

*/

// constructor
function Component()
{
    installer.installationFinished.connect(this, Component.prototype.installationFinished);
    if (component.fromOnlineRepository)
    {
        // Commented line below used by the packaging scripts
        //%IFW_DOWNLOADABLE_ARCHIVE_NAMES%
    }
}

Component.prototype.createOperations = function()
{
    component.createOperations();
    try {
        if (installer.value("SDKToolBinary") == "")
            return;
        var qmakeBinary = "@TargetDir@/%TARGET_INSTALL_DIR%/bin/qmake";

        component.addOperation("Execute",
            new Array("{1}", "@SDKToolBinary@", "addQt", "--id", component.name, "--name", "Qt %QT_VERSION%-rc1 clang 64bit (SDK)", "--type", "Qt4ProjectManager.QtVersion.Desktop", "--qmake", qmakeBinary));

        component.addOperation("Execute",
            new Array("{1}", "@SDKToolBinary@", "addKit", "--id", component.name + "_kit", "--name", "Desktop Qt %QT_VERSION%-rc1 clang 64bit (SDK)", "--toolchain", "x86-macos-generic-mach_o-64bit", "--qt", component.name, "--debuggerengine", "1", "--devicetype", "Desktop"));
    } catch(e) {
        print(e);
    }
}

Component.prototype.installationFinished = function()
{
    var assistantBinary = "@TargetDir@/%TARGET_INSTALL_DIR%/bin/Assistant.app/Contents/MacOS/Assistant";
    try {
        var myArray = installer.value("help_files").split(";");
        for (var i = 0;i < myArray.length;i++)
            installer.executeDetached(assistantBinary, new Array("-quiet", "-register", myArray[i]));
    } catch(e) {
        print(e);
    }
}

