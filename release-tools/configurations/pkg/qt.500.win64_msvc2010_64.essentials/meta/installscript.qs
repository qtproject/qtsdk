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
    if (installer.environmentVariable("VS100COMNTOOLS")) {
        return true;
    }
    return false;
}

createShortcuts = function()
{
    var qtStringVersion = "%QT_VERSION%";
    // Create a batch file with the development environment
    var component_root_path = installer.value("TargetDir") + "%TARGET_INSTALL_DIR%";
    var batchFileName = component_root_path + "/" + "bin" + "/" + "qtenv2.bat";
    var contentString = "echo off\r\n";
    contentString += "echo Setting up environment for Qt usage...\r\n";
    contentString += "set QTDIR=" + component_root_path + "\r\n";
    contentString += "set PATH=%QTDIR%\\bin;%PATH%\r\n";
    contentString += "cd /D %QTDIR%\r\n";
    contentString += "echo Remember to call vcvarsall.bat amd64 to complete environment setup!\r\n";
    // Dump batch file
    component.addOperation("AppendFile", batchFileName, contentString);

    var windir = installer.environmentVariable("WINDIR");
    if (windir == "") {
        QMessageBox["warning"]( "Error" , "Error", "Could not find windows installation directory");
        return;
    }

    var cmdLocation = windir + "\\system32\\cmd.exe";
    component.addOperation( "CreateShortcut",
                            cmdLocation,
                            "@StartMenuDir@/%QT_VERSION%/MSVC 2010 (64-bit)/Qt " + qtStringVersion + " 64-bit for Desktop (MSVC 2010).lnk",
                            "/A /Q /K " + batchFileName);
    // Assistant
    component.addOperation( "CreateShortcut",
                            component_root_path + "/bin/assistant.exe",
                            "@StartMenuDir@/%QT_VERSION%/MSVC 2010 (64-bit)/Assistant.lnk");

    // Designer
    component.addOperation( "CreateShortcut",
                            component_root_path + "/bin/designer.exe",
                            "@StartMenuDir@/%QT_VERSION%/MSVC 2010 (64-bit)/Designer.lnk");

    // Linguist
    component.addOperation( "CreateShortcut",
                            component_root_path + "/bin/linguist.exe",
                            "@StartMenuDir@/%QT_VERSION%/MSVC 2010 (64-bit)/Linguist.lnk");
}

Component.prototype.beginInstallation = function()
{
    installer.setValue(component.name + "_qtpath", "@TargetDir@" + "%TARGET_INSTALL_DIR%");
}

Component.prototype.createOperations = function()
{
    component.createOperations();

    if (installer.value("os") == "win") {
        try {
            // Create a batch file and shortcuts with the development environment
            createShortcuts();

            if (installer.value("SDKToolBinary") == "")
                return;
            var qmakeBinary = "@TargetDir@/%TARGET_INSTALL_DIR%/bin/qmake.exe";

            component.addOperation("Execute",
                new Array("{1}", "@SDKToolBinary@", "addQt", "--id", component.name, "--name", "Qt %QT_VERSION%-rc1 MSVC2010 64bit (SDK)", "--type", "Qt4ProjectManager.QtVersion.Desktop", "--qmake", qmakeBinary));

            component.addOperation("Execute",
                new Array("{1}", "@SDKToolBinary@", "addKit", "--id", component.name + "_kit", "--name", "Desktop Qt %QT_VERSION%-rc1 MSVC2010 64bit (SDK)", "--toolchain", "x86-windows-msvc2010-pe-64bit", "--qt", component.name, "--debuggerengine", "4", "--devicetype", "Desktop"));

        } catch( e ) {
            print( e );
        }
    }
}
