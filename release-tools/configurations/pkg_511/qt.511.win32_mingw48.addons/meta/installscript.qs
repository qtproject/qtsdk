/* This file is part of the Qt SDK

*/

// constructor
function Component()
{
}


checkWhetherStopProcessIsNeeded = function()
{
}


Component.prototype.createOperations = function()
{
    component.createOperations();
    component.addOperation("QtPatch",
                            "windows",
                            "@TargetDir@/%TARGET_INSTALL_DIR%",
                            "QmakeOutputInstallerKey=" + qmakeOutputInstallerKey(component),
                            "qt5");
}


Component.prototype.installationFinished = function()
{
}

