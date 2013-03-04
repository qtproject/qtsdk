/* This file is part of the Qt SDK

*/

// constructor
function Component()
{
}

Component.prototype.beginInstallation = function()
{
    var value = "";
    if (installer.value("help_files") != "")
        value = installer.value("help_files") + ";";

    installer.setValue("help_files", value + "@TargetDir@/%TARGET_INSTALL_DIR%/qt.qch");
}

Component.prototype.createOperations = function()
{
    component.createOperations();
    // this will be changed to a general settings operation in the near future
    component.addOperation("SetQtCreatorValue", "", "Help", "InstalledDocumentation", "@TargetDir@/%TARGET_INSTALL_DIR%/");
}
