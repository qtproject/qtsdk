/* This file is part of the Qt SDK

*/

// constructor
function Component()
{
    if (installer.value("os") == "mac") {
        var otoolCheck = installer.execute("/usr/bin/which", new Array("otool"))[0];
        if (!otoolCheck) {
            QMessageBox["warning"]("otoolCheckError",
                                   qsTr("No otool found!"),
                                   qsTr("You need the Xcode command line tools installed.\n" +
                                   "Download the Xcode command line tools from https://developer.apple.com/downloads\n"));
        }
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
                                    "@StartMenuDir@/Uninstall Qt 5.1.0.lnk",
                                    " --uninstall");
        } catch( e ) {
            print( e );
        }
    }
}
