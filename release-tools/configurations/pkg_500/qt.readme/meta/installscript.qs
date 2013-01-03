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

    installer.installationFinished.connect(this, Component.prototype.installationFinishedPageIsShown);
    installer.finishButtonClicked.connect(this, Component.prototype.installationFinished);
}


checkWhetherStopProcessIsNeeded = function()
{
}


Component.prototype.createOperations = function()
{
    component.createOperations();
    var component_root_path = installer.value("TargetDir") + "%TARGET_INSTALL_DIR%";

    if (installer.value("os") == "win")
    {
        var windir = installer.environmentVariable("WINDIR");
        if (windir == "") {
            QMessageBox["warning"]( "Error" , "Error", "Could not find windows installation directory");
            return;
        }

        // README
        var notePadLocation = windir + "\\notepad.exe";
        component.addOperation( "CreateShortcut",
                                notePadLocation,
                                "@StartMenuDir@/README.lnk",
                                component_root_path + "/README.txt");

        // shortcut to qt-project web page
        component.addOperation( "CreateShortcut",
                                "@TargetDir@/qt-project.org.html",
                                "@StartMenuDir@/qt-project.org.lnk");
    }
}



Component.prototype.installationFinishedPageIsShown = function()
{
    try {
        if (installer.isInstaller() && installer.status == QInstaller.Success) {
            installer.addWizardPageItem( component, "ReadMeCheckBoxForm", QInstaller.InstallationFinished );
        }
    } catch(e) {
        print(e);
    }
}

Component.prototype.installationFinished = function()
{
    try {
        if (installer.isInstaller() && installer.status == QInstaller.Success) {
            var isReadMeCheckBoxChecked = component.userInterface( "ReadMeCheckBoxForm" ).readMeCheckBox.checked;
            if (isReadMeCheckBoxChecked) {
                QDesktopServices.openUrl("file:///" + installer.value("TargetDir") + "/README.txt");
            }
        }
    } catch(e) {
        print(e);
    }
}

