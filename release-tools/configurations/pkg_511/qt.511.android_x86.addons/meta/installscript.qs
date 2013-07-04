/* This file is part of the Qt SDK

*/

// constructor
function Component()
{
}


Component.prototype.createOperations = function()
{
    component.createOperations();

    var platform = "";
    if (installer.value("os") == "x11") {
        platform = "linux";
    }
    if (installer.value("os") == "win") {
        platform = "windows";
    }
    if (installer.value("os") == "mac") {
        platform = "mac";
    }

    component.addOperation("QtPatch",
                            platform,
                            "@TargetDir@/%TARGET_INSTALL_DIR%",
                            "QmakeOutputInstallerKey=" + qmakeOutputInstallerKey(component),
                            "emb-arm");
}


