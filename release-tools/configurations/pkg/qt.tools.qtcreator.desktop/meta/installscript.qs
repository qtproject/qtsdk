/* This file is part of the Qt SDK

Copyright (c) 2011 Digia Plc and/or its subsidiary(-ies).

*/

var component_root_path = "/";
var native_path_separator = "/";

// constructor
function Component()
{
    installer.installationFinished.connect( this, Component.prototype.installationFinished );
    if (installer.value("os") == "win")
    {
        installer.setValue("QtCreatorInstallDir", "%TARGET_INSTALL_DIR%");
        component.selectedChanged.connect( this, checkWhetherStopProcessIsNeeded );
        //it can't be unselected so we need to check it manually
        checkWhetherStopProcessIsNeeded();
    }

    if ( installer.value("os") == "x11" )
    {
        // set installation directory
        installer.setValue( "EmbeddedInstallationRootDir", "/usr/local/Trolltech" );
        installer.setValue( "EmbeddedToolchainDir", "/usr/local/angstrom/arm" );
        installer.setValue("QtCreatorInstallDir", "%TARGET_INSTALL_DIR%");
    }

    if ( installer.value("os") == "mac" )
    {
        installer.setValue("QtCreatorInstallDir", "%TARGET_INSTALL_DIR%");
    }

    if ( component.fromOnlineRepository )
    {
        //%IFW_DOWNLOADABLE_ARCHIVE_NAMES%
    }
}

buildNativeComponentRootPath = function()
{
    var target_install_dir = "%TARGET_INSTALL_DIR%";
    if (installer.value("os") == "win")
        {
        native_path_separator = "\\";
        target_install_dir = target_install_dir.replace(/\//g, "\\");
        }
    else
        {
        native_path_separator = "/";
        }

    component_root_path = installer.value("TargetDir") + target_install_dir;
}

checkWhetherStopProcessIsNeeded = function()
{
    if (installer.value("os") != "win")
        return;

    var path = component_root_path + native_path_separator + "bin" + native_path_separator;
    if (component.installationRequested() || component.uninstallationRequested())
    {
        component.setStopProcessForUpdateRequest(path + "qtcreator.exe", true);
        component.setStopProcessForUpdateRequest(path + "linguist.exe", true);
        component.setStopProcessForUpdateRequest(path + "qmlviewer.exe", true);
    }
    else
    {
        component.setStopProcessForUpdateRequest(path + "qtcreator.exe", false);
        component.setStopProcessForUpdateRequest(path + "linguist.exe", false);
        component.setStopProcessForUpdateRequest(path + "qmlviewer.exe", false);
    }
}

registerWindowsFileTypeExtensions = function()
{
    var headerExtensions = new Array("h", "hh", "hxx", "h++", "hpp", "hpp");
    var path = component_root_path + native_path_separator + "bin" + native_path_separator;

    for (var i = 0; i < headerExtensions.length; ++i) {
        component.addOperation( "RegisterFileType",
                                headerExtensions[i],
                                path + "qtcreator.exe -client '%1'",
                                "C++ Header file",
                                "",
                                path + "qtcreator.exe,3");
    }

    var cppExtensions = new Array("cc", "cxx", "c++", "cp", "cpp");

    for (var i = 0; i < cppExtensions.length; ++i) {
        component.addOperation( "RegisterFileType",
                                cppExtensions[i],
                                path + "qtcreator.exe -client '%1'",
                                "C++ Source file",
                                "",
                                path + "qtcreator.exe,2");
    }

    component.addOperation( "RegisterFileType",
                            "c",
                            path + "qtcreator.exe -client '%1'",
                            "C Source file",
                            "",
                            path + "qtcreator.exe,1");
    component.addOperation( "RegisterFileType",
                            "ui",
                            path + "qtcreator.exe -client '%1'",
                            "Qt UI file",
                            "",
                            path + "qtcreator.exe,4");
    component.addOperation( "RegisterFileType",
                            "pro",
                            path + "qtcreator.exe -client '%1'",
                            "Qt Project file",
                            "",
                            path + "qtcreator.exe,5");
    component.addOperation( "RegisterFileType",
                            "pri",
                            path + "qtcreator.exe -client '%1'",
                            "Qt Project Include file",
                            "",
                            path + "qtcreator.exe,6");
    component.addOperation( "RegisterFileType",
                            "qs",
                            path + "qtcreator.exe -client '%1'",
                            "Qt Script file",
                            "",
                            path + "qtcreator.exe,0");
    component.addOperation( "RegisterFileType",
                            "qml",
                            path + "qtcreator.exe -client '%1'",
                            "Qt Quick Markup language file",
                            "",
                            path + "qtcreator.exe,0");
}

Component.prototype.createOperations = function()
{
    // Call the base createOperations and afterwards set some registry settings
    component.createOperations();
    buildNativeComponentRootPath();
    var path = component_root_path + native_path_separator;

    if ( installer.value("os") == "win" )
    {
        component.addOperation( "SetPluginPathOnQtCore",
                                path + "bin",
                                path + "plugins");
        component.addOperation( "SetImportsPathOnQtCore",
                                path + "bin",
                                path + "bin");
        component.addOperation( "CreateShortcut",
                                path + "bin" + native_path_separator + "qtcreator.exe",
                                "@StartMenuDir@\\Qt Creator.lnk",
                                "workingDirectory=" + path + "bin");

        registerWindowsFileTypeExtensions();
    }
    if ( installer.value("os") == "x11" )
    {
        component.addOperation( "SetPluginPathOnQtCore",
                                path + "lib" + native_path_separator + "qtcreator",
                                path + "lib" + native_path_separator + "qtcreator" + native_path_separator + "plugins");
        component.addOperation( "SetImportsPathOnQtCore",
                                path + "lib" + native_path_separator + "qtcreator",
                                path + "bin");
        component.addOperation( "InstallIcons", path + "icons" );
        component.addOperation( "CreateDesktopEntry",
                                "qtcreator.desktop",
                                "Type=Application\nExec=" + path + "bin" + native_path_separator + "qtcreator\nPath=@homeDir@\nName=Qt Commercial Creator\nGenericName=The IDE of choice for development on Qt.\nIcon=Digia-QtCreator\nTerminal=false\nCategories=Development;IDE;Qt;\nMimeType=text/x-c++src;text/x-c++hdr;text/x-xsrc;application/x-designer;application/vnd.nokia.qt.qmakeprofile;application/vnd.nokia.xml.qt.resource;"
                                );
    }
    if (installer.value("os") == "mac")
    {
    }
}

Component.prototype.installationFinished = function()
{
    if (installer.isInstaller() && component.selected)
    {
        var path = component_root_path + native_path_separator;
        if (installer.value("os") == "win")
        {
            installer.setValue("RunProgram", path + "bin" + native_path_separator + "qtcreator.exe");
        }
        else if (installer.value("os") == "x11")
        {
            installer.setValue("RunProgram", path + "bin" + native_path_separator + "qtcreator");
        }
        else if (installer.value("os") == "mac")
        {
            installer.setValue("RunProgram", "\"" + installer.value("TargetDir") + "/Qt Creator.app/Contents/MacOS/Qt Creator\"");
        }
        installer.setValue("RunProgramDescription", "Launch Qt Creator");
    }
}

