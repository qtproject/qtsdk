/* This file is part of the Qt SDK

*/

// constructor
function Component()
{
}



Component.prototype.createOperations = function()
{
    component.createOperations();
    component.addOperation("QtPatch",
                            "mac",
                            "@TargetDir@/%TARGET_INSTALL_DIR%",
                            "QmakeOutputInstallerKey=" + qmakeOutputInstallerKey(component),
                            "qt5");
}


