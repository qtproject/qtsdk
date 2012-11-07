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
        if (installer.value("os") == "mac") {
            // patch Qt binaries
            component.addOperation( "QtPatch", "mac", "@TargetDir@/%TARGET_INSTALL_DIR%" );
        }
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

