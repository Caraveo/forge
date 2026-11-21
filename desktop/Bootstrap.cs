using System;
using System.IO;
using System.Reflection;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Windows.Forms;
internal static class Forge {
    [DllImport("msi.dll", CharSet=CharSet.Unicode)]
    static extern int MsiQueryProductState(string productCode);
    [DllImport("msi.dll", CharSet=CharSet.Unicode)]
    static extern uint MsiGetProductInfo(string product, string property, System.Text.StringBuilder value, ref uint length);
    public static string Quote(string s){return "\""+s+"\"";}
    // Windows Installer remembers the file name a product was installed from, and its
    // SecureRepair check fails (1603) if a repair runs from a package with another name.
    // Reuse the installed product's package name, or the release name for a fresh install.
    static string PackageName(bool installed){
        if(installed){
            var value=new System.Text.StringBuilder(260);uint length=260;
            if(MsiGetProductInfo(BuildInfo.ProductCode,"PackageName",value,ref length)==0){
                string name=Path.GetFileName(value.ToString());
                if(name.Length>0&&name.EndsWith(".msi",StringComparison.OrdinalIgnoreCase)&&name.IndexOfAny(Path.GetInvalidFileNameChars())<0)return name;
            }
        }
        return BuildInfo.MsiName;
    }
    [STAThread] static int Main(){
        try{
            Hardware.Check();
            if(MessageBox.Show("FORGE will install its own application and private Python/ROCm environment under your Windows profile. First setup downloads model weights and supporting tools. It will not replace files in your existing AI projects.\n\nUninstall removes FORGE's private runtime and app. Generated models and downloaded weights are kept.\n\nRequires an AMD CPU and GPU, 16 GB dedicated VRAM and 32 GB RAM. Continue?","FORGE Setup - Before you install",MessageBoxButtons.OKCancel,MessageBoxIcon.Warning)!=DialogResult.OK)return 1602;
            // Older builds are replaced by the MSI's major upgrade. Only this exact
            // build being installed already (state 5) needs an explicit repair.
            bool installed = MsiQueryProductState(BuildInfo.ProductCode) == 5;
            string dir=Path.Combine(Path.GetTempPath(),"FORGE-"+Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(dir);string path=Path.Combine(dir,PackageName(installed));
            try{
                using(var input=Assembly.GetExecutingAssembly().GetManifestResourceStream("FORGE.msi"))
                using(var output=File.Create(path))input.CopyTo(output);
                string repair = installed ? " REINSTALL=ALL REINSTALLMODE=vamus" : "";
                string data=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"FORGE-Data");
                Directory.CreateDirectory(data);string log=Path.Combine(data,"install.log");
                using(var p=Process.Start("msiexec.exe","/i "+Quote(path)+repair+" /passive /norestart /l*v "+Quote(log))){
                    p.WaitForExit();
                    if(p.ExitCode!=0&&p.ExitCode!=3010){
                        MessageBox.Show("Windows Installer stopped with code "+p.ExitCode+".\n\nDetails are in "+log,"FORGE Setup");
                        return p.ExitCode;
                    }
                }
                string local=Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                if(!Setup.Ready(Path.Combine(local,"Programs","FORGE")))Setup.Install(Path.Combine(local,"Programs","FORGE"));
                MessageBox.Show("FORGE is ready. Open it from Start.","FORGE Setup");return 0;
            }finally{File.Delete(path);Directory.Delete(dir);}
        }catch(Exception e){MessageBox.Show(e.Message,"FORGE Setup");return 1;}
    }
}
