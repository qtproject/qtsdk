/* This file is part of the Qt SDK

*/

// constructor
function Component()
{
}

Component.prototype.isDefault = function()
{
    if (installer.environmentVariable("VS100COMNTOOLS")) {
        return true;
    }
    return false;
}

function createShortcuts()
{
    var qtStringVersion = "5.1.1";
    // Create a batch file with the development environment
    var component_root_path = installer.value("TargetDir") + "%TARGET_INSTALL_DIR%";
    component_root_path = component_root_path.replace(/\//g, "\\");

    var batchFileName = component_root_path + "\\" + "bin" + "\\" + "qtenv2.bat";
    var contentString = "echo off\r\n";
    contentString += "echo Setting up environment for Qt usage...\r\n";
    contentString += "set PATH="  + component_root_path + "\\bin;%PATH%\r\n";
    contentString += "cd /D " + component_root_path + "\r\n";
    contentString += "echo Remember to call vcvarsall.bat to complete environment setup!\r\n";
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
                            "@StartMenuDir@/5.1.1/MSVC 2010 OpenGL/Qt " + qtStringVersion + " for Desktop (MSVC 2010 OpenGL).lnk",
                            "/A /Q /K " + batchFileName);
    // Assistant
    component.addOperation( "CreateShortcut",
                            component_root_path + "/bin/assistant.exe",
                            "@StartMenuDir@/5.1.1/MSVC 2010 OpenGL/Assistant.lnk");

    // Designer
    component.addOperation( "CreateShortcut",
                            component_root_path + "/bin/designer.exe",
                            "@StartMenuDir@/5.1.1/MSVC 2010 OpenGL/Designer.lnk");

    // Linguist
    component.addOperation( "CreateShortcut",
                            component_root_path + "/bin/linguist.exe",
                            "@StartMenuDir@/5.1.1/MSVC 2010 OpenGL/Linguist.lnk");
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
            var qtPath = "@TargetDir@/%TARGET_INSTALL_DIR%";
            var qmakeBinary = "@TargetDir@/%TARGET_INSTALL_DIR%/bin/qmake.exe";
            addInitQtPatchOperation(component, "windows", qtPath, qmakeBinary, "qt5");

            // Create a batch file and shortcuts with the development environment
            createShortcuts();

            if (installer.value("SDKToolBinary") == "")
                return;

            component.addOperation("Execute",
                new Array("{0}", "@SDKToolBinary@", "addQt", "--id", component.name, "--name", "Qt 5.1.1 MSVC2010 32bit OpenGL", "--type", "Qt4ProjectManager.QtVersion.Desktop", "--qmake", qmakeBinary));

            component.addOperation("Execute",
                new Array("{0}", "@SDKToolBinary@", "addKit", "--id", component.name + "_kit", "--name", "Desktop Qt 5.1.1 MSVC2010 32bit OpenGL", "--toolchain", "x86-windows-msvc2010-pe-32bit", "--qt", component.name, "--debuggerengine", "4", "--devicetype", "Desktop"));

        } catch( e ) {
            print( e );
        }
    }
}
