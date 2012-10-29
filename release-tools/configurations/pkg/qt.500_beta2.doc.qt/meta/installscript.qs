/* This file is part of the Qt SDK

*/

// constructor
function Component()
{
    installer.installationFinished.connect( this, Component.prototype.installationFinished );
    if (component.fromOnlineRepository)
    {
        // Commented line below used by the packaging scripts
        //%IFW_DOWNLOADABLE_ARCHIVE_NAMES%
    }
}


checkWhetherStopProcessIsNeeded = function()
{
}


Component.prototype.createOperations = function()
{
    component.createOperations();
}


Component.prototype.installationFinished = function()
{
    // If assistant binary exists, register documentation
    if (installer.value("AssistantBinary")) {
        try {
            print("Registering documentation..")
            var operation = "-quiet -register ";
            var qchFile = installer.value("TargetDir") + "%TARGET_INSTALL_DIR%" + "/qt.qch";
            installer.execute(installer.value("AssistantBinary"), new Array(operation + installer.value(qchFile)));
        } catch( e ) {
            print( e );
        }
    }
    else {
        print("No assistant binary available -> not registering the documentation.")
    }
}
