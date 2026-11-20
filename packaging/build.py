"""Windows x64 build host: CPython 3.12 (msilib) and inbox .NET Framework."""
import os
import shutil
import subprocess
import sys
from pathlib import Path
import msilib as m
from msilib import schema, sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "desktop"
DIST = ROOT / "dist"
APP = DIST / "app"
APP.mkdir(parents=True, exist_ok=True)
FRAME = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319"


def compile_exe(dest, sources, options):
    subprocess.run([str(FRAME / "csc.exe"), "/nologo", "/target:winexe", "/platform:x64",
                    "/optimize+", "/out:" + str(dest), *options, *map(str, sources)], check=True)


compile_exe(APP / "FORGE.exe", [SRC / f for f in ("Forge.cs","Preview.cs","Setup.cs")],
            ["/r:" + str(FRAME / "WPF" / f) for f in ("PresentationFramework.dll","PresentationCore.dll","WindowsBase.dll")]
            + ["/r:System.Xaml.dll","/r:System.Web.Extensions.dll","/r:Microsoft.CSharp.dll"])
files = ["FORGE.exe","runner.py","flux_generate.py","transit_blender.py","setup-runtime.ps1","cli.ps1","prompt_enhancer.py"]
for f in files[1:]:
    shutil.copy2((ROOT/"model_forge_local" if f=="prompt_enhancer.py" else SRC)/f,APP/f)
for command,mode in (("forge","model"),("generate","image"),("enhance","enhance")):
    name=command+".cmd"
    (APP/name).write_text('@echo off\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0cli.ps1" '+mode+' %*\nexit /b %errorlevel%\n')
    files.append(name)

product="{CF2D1558-B4EC-4798-983C-5A519BC65805}"
msi = DIST / "FORGE-v0.01-x64.msi"
db=m.init_database(str(msi),schema,"FORGE",product,"0.1.0","Caraveo")
m.add_tables(db,sequence)
m.add_data(db,"Property",[("MSIINSTALLPERUSER","1"),("ARPNOMODIFY","1"),("UpgradeCode","{D7543330-665D-4D0A-A028-550218D91288}")])
cab=m.CAB("payload")
top=m.Directory(db,cab,None,str(APP),"TARGETDIR","SourceDir")
local=m.Directory(db,cab,top,".","LocalAppDataFolder",".")
programs=m.Directory(db,cab,local,".","PrivatePrograms","Programs")
dest=m.Directory(db,cab,programs,".","ForgeApp","FORGE")
menu=m.Directory(db,cab,top,".","ProgramMenuFolder",".")
feature=m.Feature(db,"Desktop","Desktop","FORGE",1)
dest.start_component("ForgeFiles",feature,0,keyfile="FORGE.exe")
for f in files: dest.add_file(f,str(APP/f))
m.add_data(db,"Shortcut",[("LaunchForge","ProgramMenuFolder","FORGE","ForgeFiles","[#FORGE.exe]",None,"Open FORGE",None,None,None,1,"ForgeApp")])
# Binary table (distinct from the embedded cabinet stream).
m.add_data(db,"Binary",[("Probe",m.Binary(str(APP/"FORGE.exe")))])
m.add_data(db,"CustomAction",[("CheckHardware",2,"Probe","--check"),("CleanRuntime",18,"FORGE.exe","--remove-runtime")])
m.add_data(db,"InstallExecuteSequence",[("CheckHardware","NOT Installed",799),("CleanRuntime",'REMOVE~="ALL"',3499)])
cab.commit(db);db.Commit();db.Close()
compile_exe(DIST/"FORGE-v0.01-Setup.exe",[SRC/"Bootstrap.cs",SRC/"Setup.cs"],
            ["/r:System.Windows.Forms.dll","/resource:"+str(msi)+",FORGE.msi"])
print(DIST/"FORGE-v0.01-Setup.exe")
