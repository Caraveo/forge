"""Windows x64 build host: CPython 3.12 (msilib) and inbox .NET Framework."""
import argparse
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
import msilib as m
from msilib import schema, sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "desktop"
DIST = ROOT / "dist"
parser = argparse.ArgumentParser()
parser.add_argument("--app-dir", type=Path, default=DIST / "payload")
APP = parser.parse_args().app_dir.resolve()
APP.mkdir(parents=True, exist_ok=True)
FRAME = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319"


def compile_exe(dest, sources, options):
    subprocess.run([str(FRAME / "csc.exe"), "/nologo", "/target:winexe", "/platform:x64",
                    "/optimize+", "/out:" + str(dest), *options, *map(str, sources)], check=True)


ICON = SRC / "forge.ico"  # regenerate with packaging/make-icon.py
compile_exe(APP / "FORGE.exe", [SRC / f for f in ("Forge.cs","Preview.cs","Setup.cs","Intent.cs")],
            ["/r:" + str(FRAME / "WPF" / f) for f in ("PresentationFramework.dll","PresentationCore.dll","WindowsBase.dll")]
            + ["/r:System.Xaml.dll","/r:System.Web.Extensions.dll","/r:Microsoft.CSharp.dll",
               "/win32icon:" + str(ICON), "/resource:" + str(ICON) + ",forge.ico"])
files = ["FORGE.exe","runner.py","flux_generate.py","transit_blender.py","setup-runtime.ps1","cli.ps1","prompt_enhancer.py","rig.ps1","chat.py","setup-extras.py","manifest-v004.json"]
for f in files[1:]:
    shutil.copy2((ROOT/"model_forge_local" if f=="prompt_enhancer.py" else SRC)/f,APP/f)
for command,mode in (("forge","model"),("generate","image"),("enhance","enhance"),("upscale","upscale"),("background","background")):
    name=command+".cmd"
    (APP/name).write_text('@echo off\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0cli.ps1" '+mode+' %*\nexit /b %errorlevel%\n')
    files.append(name)
(APP/'rig.cmd').write_text('@echo off\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0rig.ps1" %*\nexit /b %errorlevel%\n')
files.append('rig.cmd')

# Every build is a major upgrade: a fresh ProductCode under the fixed UpgradeCode.
# Reusing one ProductCode across versions turned upgrades into repairs, which
# Windows Installer's SecureRepair rejects (errors 1625/1603).
VERSION = "0.4.0"
upgrade = "{D7543330-665D-4D0A-A028-550218D91288}"
product = "{" + str(uuid.uuid4()).upper() + "}"
msi = DIST / "FORGE-v0.04-x64.msi"
db=m.init_database(str(msi),schema,"FORGE",product,VERSION,"Caraveo")
m.add_tables(db,sequence)
# REINSTALLMODE "a" forces every file to be copied. Without it, costing sees the
# previous build's files (same versions) and plans no copy, and then
# RemoveExistingProducts deletes them, leaving an empty install folder.
m.add_data(db,"Property",[("MSIINSTALLPERUSER","1"),("REINSTALLMODE","amus"),("ARPNOMODIFY","1"),("UpgradeCode",upgrade),
                          ("SecureCustomProperties","OLDFORGE;NEWERFORGE")])
m.add_data(db,"Upgrade",[(upgrade,None,VERSION,None,512,None,"OLDFORGE"),
                         (upgrade,VERSION,None,None,2,None,"NEWERFORGE")])
m.add_data(db,"LaunchCondition",[("NOT NEWERFORGE","A newer version of FORGE is already installed.")])
# Remove the old product before installing files, so component contents never overlap.
view=db.OpenView("UPDATE `InstallExecuteSequence` SET `Sequence`=1401 WHERE `Action`='RemoveExistingProducts'")
view.Execute(None);view.Close();del view  # a live view handle keeps the MSI file locked
cab=m.CAB("payload")
top=m.Directory(db,cab,None,str(APP),"TARGETDIR","SourceDir")
local=m.Directory(db,cab,top,".","LocalAppDataFolder",".")
programs=m.Directory(db,cab,local,".","PrivatePrograms","Programs")
dest=m.Directory(db,cab,programs,".","ForgeApp","FORGE")
menu=m.Directory(db,cab,top,".","ProgramMenuFolder",".")
feature=m.Feature(db,"Desktop","Desktop","FORGE",1)
dest.start_component("ForgeFiles",feature,0,keyfile="FORGE.exe",uuid="{3ED3BBCF-3D8D-4440-B35C-7451A8C3D790}")
for f in files: dest.add_file(f,str(APP/f))
m.add_data(db,"Icon",[("ForgeIcon.exe",m.Binary(str(ICON)))])
m.add_data(db,"Property",[("ARPPRODUCTICON","ForgeIcon.exe")])
m.add_data(db,"Shortcut",[("LaunchForge","ProgramMenuFolder","FORGE","ForgeFiles","[#FORGE.exe]",None,"Open FORGE",None,"ForgeIcon.exe",0,1,"ForgeApp")])
# Binary table (distinct from the embedded cabinet stream).
m.add_data(db,"Binary",[("Probe",m.Binary(str(APP/"FORGE.exe")))])
# Older packages delete the private runtime on any uninstall, including the one
# RemoveExistingProducts performs. Hide the ownership marker so that removal is a
# no-op, then restore it once the new version is installed.
m.add_data(db,"CustomAction",[("CheckHardware",2,"Probe","--check"),("CleanRuntime",18,"FORGE.exe","--remove-runtime"),
                              ("PreserveRuntime",2,"Probe","--preserve-runtime"),("RestoreRuntime",2,"Probe","--restore-runtime")])
m.add_data(db,"InstallExecuteSequence",[("CheckHardware","NOT Installed",799),
                                        ("PreserveRuntime","OLDFORGE",1390),
                                        ("CleanRuntime",'REMOVE~="ALL" AND NOT UPGRADINGPRODUCTCODE',3499),
                                        ("RestoreRuntime","OLDFORGE",6650)])
cab.commit(db);db.Commit();db.Close()
build_info = DIST / "BuildInfo.cs"
build_info.write_text('internal static class BuildInfo { public const string ProductCode="' + product + '"; }\n')
compile_exe(DIST/"FORGE-v0.04-Setup.exe",[SRC/"Bootstrap.cs",SRC/"Setup.cs",build_info],
            ["/r:System.Windows.Forms.dll","/resource:"+str(msi)+",FORGE.msi","/win32icon:"+str(ICON)])
print(DIST/"FORGE-v0.04-Setup.exe")
