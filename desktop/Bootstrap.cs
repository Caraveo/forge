using System;
using System.IO;
using System.Reflection;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Windows.Forms;
internal static class Forge {
    [DllImport("msi.dll", CharSet=CharSet.Unicode)]
    static extern int MsiQueryProductState(string productCode);
    public static string Quote(string s){return "\""+s+"\"";}
    [STAThread] static int Main(){
        try{
            Hardware.Check();
            if(MessageBox.Show("FORGE will install its own application and private Python/ROCm environment under your Windows profile. First setup downloads model weights and supporting tools. It will not replace files in your existing AI projects.\n\nUninstall removes FORGE's private runtime and app. Generated models and downloaded weights are kept.\n\nRequires an AMD CPU and GPU, 16 GB dedicated VRAM and 32 GB RAM. Continue?","FORGE Setup - Before you install",MessageBoxButtons.OKCancel,MessageBoxIcon.Warning)!=DialogResult.OK)return 1602;
            string dir=Path.Combine(Path.GetTempPath(),"FORGE-"+Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(dir);string path=Path.Combine(dir,"FORGE.msi");
            try{
                using(var input=Assembly.GetExecutingAssembly().GetManifestResourceStream("FORGE.msi"))
                using(var output=File.Create(path))input.CopyTo(output);
                bool installed = MsiQueryProductState("{CF2D1558-B4EC-4798-983C-5A519BC65805}") == 5;
                string repair = installed ? " REINSTALL=ALL REINSTALLMODE=vamus" : "";
                using(var p=Process.Start("msiexec.exe","/i "+Quote(path)+repair+" /passive /norestart")){
                    p.WaitForExit();
                    if(p.ExitCode!=0){
                        MessageBox.Show("Windows Installer returned code "+p.ExitCode+".","FORGE Setup");
                        return p.ExitCode;
                    }
                }
                string local=Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                if(!File.Exists(Path.Combine(local,"FORGE-Data","runtime","config.json")))Setup.Install(Path.Combine(local,"Programs","FORGE"));
                MessageBox.Show("FORGE is ready. Open it from Start.","FORGE Setup");return 0;
            }finally{File.Delete(path);Directory.Delete(dir);}
        }catch(Exception e){MessageBox.Show(e.Message,"FORGE Setup");return 1;}
    }
}
