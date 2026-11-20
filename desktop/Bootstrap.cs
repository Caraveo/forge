using System;
using System.IO;
using System.Reflection;
using System.Diagnostics;
using System.Windows.Forms;
internal static class Forge {
    public static string Quote(string s){return "\""+s+"\"";}
    [STAThread] static int Main(){
        try{
            Hardware.Check();
            if(MessageBox.Show("Install FORGE for your Windows account?\n\nRequires AMD CPU and GPU, 16 GB dedicated VRAM and 32 GB RAM. Setup downloads a private Python runtime, generation tools and model weights.","FORGE Setup",MessageBoxButtons.OKCancel)!=DialogResult.OK)return 1602;
            string dir=Path.Combine(Path.GetTempPath(),"FORGE-"+Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(dir);string path=Path.Combine(dir,"FORGE.msi");
            try{
                using(var input=Assembly.GetExecutingAssembly().GetManifestResourceStream("FORGE.msi"))
                using(var output=File.Create(path))input.CopyTo(output);
                using(var p=Process.Start("msiexec.exe","/i "+Quote(path)+" /passive")){p.WaitForExit();if(p.ExitCode!=0)return p.ExitCode;}
                string local=Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                if(!File.Exists(Path.Combine(local,"FORGE Data","runtime","config.json")))Setup.Install(Path.Combine(local,"Programs","FORGE"));
                MessageBox.Show("FORGE is ready. Open it from Start.","FORGE Setup");return 0;
            }finally{File.Delete(path);Directory.Delete(dir);}
        }catch(Exception e){MessageBox.Show(e.Message,"FORGE Setup");return 1;}
    }
}
