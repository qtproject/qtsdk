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


checkWhetherStopProcessIsNeeded = function()
{
}


Component.prototype.createOperations = function()
{
    component.createOperations();

    if (installer.value("os") == "x11") {
        try {
            // patch Qt binaries
            component.addOperation( "QtPatch", "linux", installer.value("TargetDir") + "%TARGET_INSTALL_DIR%" );
        } catch( e ) {
            print( e );
        }

        try {
            // set assistant binary path
            var assistantBinary = installer.value("TargetDir") + "/Desktop/Qt/5.0.0-beta2/gcc_64" + "/bin/assistant";
            installer.setValue("AssistantBinary", assistantBinary);
        } catch( e ) {
            print( e );
        }
    }
    if (installer.value("os") == "mac") {
        try {
            // patch Qt binaries
            component.addOperation( "QtPatch", "mac", installer.value("TargetDir") + "%TARGET_INSTALL_DIR%" );
        } catch( e ) {
            print( e );
        }

        try {
            // set assistant binary path
            var assistantBinary = installer.value("TargetDir") + "%TARGET_INSTALL_DIR%" + "/bin/Assistant.app/Contents/MacOS/Assistant";
            installer.setValue("AssistantBinary", assistantBinary);
        } catch( e ) {
            print( e );
        }
    }
    if (installer.value("os") == "win") {
        try {
            // patch Qt binaries
            component.addOperation( "QtPatch", "windows", installer.value("TargetDir") + "%TARGET_INSTALL_DIR%" );
        } catch( e ) {
            print( e );
        }

        try {
            // set assistant binary path
            var assistantBinary = installer.value("TargetDir") + "%TARGET_INSTALL_DIR%" + "/bin/assistant.exe";
            installer.setValue("AssistantBinary", assistantBinary);
        } catch( e ) {
            print( e );
        }
    }
}


Component.prototype.installationFinished = function()
{
}

