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

Component.prototype.createOperations = function()
{
    component.createOperations();

    if (installer.value("os") == "win") {
        try {
            var win_application = installer.value("TargetDir") + "/MaintenanceTool.exe";

            component.addOperation( "CreateShortcut",
                                    win_application,
                                    "@StartMenuDir@/Uninstall Qt 5.0.0 Beta2.lnk",
                                    " --uninstall");
        } catch( e ) {
            print( e );
        }
    }
}


Component.prototype.installationFinished = function()
{
}

