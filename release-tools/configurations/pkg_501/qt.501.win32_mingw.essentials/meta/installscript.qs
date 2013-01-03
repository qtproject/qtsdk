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

    if (installer.value("os") == "win") {
        try {
            if (installer.value("SDKToolBinary") == "")
                return;
            var qmakeBinary = "@TargetDir@/%TARGET_INSTALL_DIR%/bin/qmake.exe";

            component.addOperation("Execute",
                new Array("{1}", "@SDKToolBinary@", "addQt", "--id", component.name, "--name", "Qt %QT_VERSION% MinGW 32bit (SDK)", "--type", "Qt4ProjectManager.QtVersion.Desktop", "--qmake", qmakeBinary));

            component.addOperation("Execute",
                new Array("{1}", "@SDKToolBinary@", "addKit", "--id", component.name + "_kit", "--name", "Desktop Qt %QT_VERSION% MinGW 32bit (SDK)", "--toolchain", "x86-windows-msys-pe-32bit", "--qt", component.name, "--debuggerengine", "1", "--devicetype", "Desktop"));

        } catch( e ) {
            print( e );
        }
    }
}
