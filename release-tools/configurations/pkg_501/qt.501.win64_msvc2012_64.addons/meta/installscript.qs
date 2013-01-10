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


Component.prototype.isDefault = function()
{
    if (installer.environmentVariable("VS110COMNTOOLS")) {
        return true;
    }
    return false;
}


Component.prototype.createOperations = function()
{
    component.createOperations();
}


