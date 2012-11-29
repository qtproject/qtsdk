/* This file is part of the Qt SDK

*/





function Component()
{
    if (installer.isInstaller()) {
        installer.aboutCalculateComponentsToInstall.connect( this, addDynamicDependencies );
    }
}

addDynamicDependencies = function(page)
{
    if (page <= QInstaller.ComponentSelection)
        return;
    component.setValue("Dependencies", "");
    var dynamicDependencies = new Array();
    dynamicDependencies.push("qt.500.gcc_64.essentials");
    dynamicDependencies.push("qt.500.gcc_64.addons");
    dynamicDependencies.push("qt.500.gcc.essentials");
    dynamicDependencies.push("qt.500.gcc.addons");
    dynamicDependencies.push("qt.500.clang_64.essentials");
    dynamicDependencies.push("qt.500.clang_64.addons");
    dynamicDependencies.push("qt.500.win32_mingw.addons");
    dynamicDependencies.push("qt.500.win32_mingw.essentials");
    dynamicDependencies.push("qt.500.win32_msvc2010.essentials");
    dynamicDependencies.push("qt.500.win32_msvc2010.addons");
    dynamicDependencies.push("qt.500.win32_msvc2010_64.essentials");
    dynamicDependencies.push("qt.500.win32_msvc2010_64.addons");

    for (var i = 0; i < dynamicDependencies.length; i++) {
        componentName = dynamicDependencies[i];
        if (installer.componentByName(componentName) &&
            installer.componentByName(componentName).installationRequested()) {
            component.addDependency(componentName);
            print(componentName + " added");
        }
    }
}
/**
TODO: separate patcher needed for each qt version if online repositories are to be used
*/
Component.prototype.createOperations = function()
{
    component.createOperations();

    if (installer.value("os") == "x11") {
        try {
            // patch Qt binaries
            if (installer.value("qt.500.gcc_64.essentials_qtpath"))
                component.addOperation("QtPatch", "linux", installer.value("qt.500.gcc_64.essentials_qtpath"));
            if (installer.value("qt.500.gcc.essentials_qtpath"))
                component.addOperation("QtPatch", "linux", installer.value("qt.500.gcc.essentials_qtpath"));
        } catch( e ) {
            print( e );
        }
    }

    if (installer.value("os") == "win") {
        try {
            // patch Qt binaries
            if (installer.value("qt.500.win32_mingw.essentials_qtpath"))
                component.addOperation("QtPatch", "windows", installer.value("qt.500.win32_mingw.essentials_qtpath"));
            if (installer.value("qt.500.win32_msvc2010.essentials_qtpath"))
                component.addOperation("QtPatch", "windows", installer.value("qt.500.win32_msvc2010.essentials_qtpath"));
            if (installer.value("qt.500.win32_msvc2010_64.essentials_qtpath"))
                component.addOperation("QtPatch", "windows", installer.value("qt.500.win32_msvc2010_64.essentials_qtpath"));
        } catch( e ) {
            print( e );
        }
    }

    if (installer.value("os") == "mac") {
        try {
            // patch Qt binaries
            component.addOperation("QtPatch", "mac", installer.value("qt.500.clang_64.essentials_qtpath"));
        } catch( e ) {
            print( e );
        }
    }
}

