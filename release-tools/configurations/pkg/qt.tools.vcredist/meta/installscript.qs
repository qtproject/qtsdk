
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
    // Call the base createOperations and afterwards set some registry settings
    // so that the simulator finds its fonts and applications find the simulator
    component.createOperations();

    //return value 3010 means it need a reboot, but in most cases it is not needed for run Qt application
    component.addElevatedOperation("Execute", "{0,3010}", "@TargetDir@\\vcredist\\vcredist_x86.exe", "/norestart", "/q");
}
