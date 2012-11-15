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

    if (installer.value("os") == "win") {
        try {
            // patch Qt binaries
            component.addOperation("QtPatch", "windows", "@TargetDir@/%TARGET_INSTALL_DIR%");

            if (installer.value("SDKToolBinary") == "")
                return;
            var qmakeBinary = "@TargetDir@/%TARGET_INSTALL_DIR%/bin/qmake.exe";

            component.addOperation("Execute",
                new Array("{1}", "@SDKToolBinary@", "addQt", "--id", component.name, "--name", "Qt %QT_VERSION% beta2 MinGW 32bit (SDK)", "--type", "Qt4ProjectManager.QtVersion.Desktop", "--qmake", qmakeBinary));

            component.addOperation("Execute",
                new Array("{1}", "@SDKToolBinary@", "addKit", "--id", component.name + "_kit", "--name", "Desktop Qt %QT_VERSION% beta2 MinGW 32bit (SDK)", "--toolchain", "x86-windows-msys-pe-32bit", "--qt", component.name, "--debuggerengine", "1", "--devicetype", "Desktop"));

        } catch( e ) {
            print( e );
        }
    }
}

Component.prototype.installationFinished = function()
{
    if (!component.installed)
        return;
    var assistantBinary = "@TargetDir@/%TARGET_INSTALL_DIR%/bin/assistant.exe";
    try {
        var myArray = installer.value("help_files").split(";");
        for (var i = 0; i < myArray.length; i++)
            installer.executeDetached(assistantBinary, new Array("-quiet", "-register", myArray[i]));
    } catch(e) {
        print(e);
    }
}
