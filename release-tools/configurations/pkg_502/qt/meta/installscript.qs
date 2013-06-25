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

    gui.pageWidgetByObjectName("LicenseAgreementPage").entered.connect(changeLicenseLabels);
}

changeLicenseLabels = function()
{
    page = gui.pageWidgetByObjectName("LicenseAgreementPage");
    page.AcceptLicenseLabel.setText("I h<u>a</u>ve read and agree to the following terms contained in the license agreements accompanying the Qt 5.0.2 installer and additional items. I agree that my use of the Qt 5.0.2 installer is governed by the terms and conditions contained in these license agreements.");
    page.RejectLicenseLabel.setText("I <u>d</u>o not accept the terms and conditions of the above listed license agreements. Please note by checking the box, you must cancel the installation or downloading the Qt 5.0.2 and must destroy all copies, or portions thereof, of the Qt 5.0.2 in your possessions.");
}

qmakeOutputInstallerKey = function(aComponent)
{
    var qmakeOutputInstallerKey = aComponent.name;
    // try to find the parent
    if (qmakeOutputInstallerKey.lastIndexOf(".") !== -1) {
        qmakeOutputInstallerKey = qmakeOutputInstallerKey.slice(0, qmakeOutputInstallerKey.lastIndexOf("."));
    }
    qmakeOutputInstallerKey += "_qmakeoutput";
    return qmakeOutputInstallerKey;
}

addInitQtPatchOperation = function(aComponent, aOS, aQtPath, aQmakePath, version)
{
    aComponent.addOperation("ConsumeOutput", qmakeOutputInstallerKey(aComponent), aQmakePath, "-query");
    aComponent.addOperation("QtPatch", aOS, aQtPath, version);
}

Component.prototype.createOperations = function()
{
    component.createOperations();

    if (installer.value("os") == "win") {
        try {
            var win_application = installer.value("TargetDir") + "/MaintenanceTool.exe";

            component.addOperation( "CreateShortcut",
                                    win_application,
                                    "@StartMenuDir@/Uninstall Qt 5.0.2.lnk",
                                    " --uninstall");
        } catch( e ) {
            print( e );
        }
    }
}
