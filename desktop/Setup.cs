using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using Microsoft.Win32;

internal static class Hardware {
    [DllImport("kernel32")] static extern bool GetPhysicallyInstalledSystemMemory(out ulong kb);
    [DllImport("dxgi")] static extern int CreateDXGIFactory1(ref Guid id,out IntPtr factory);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int EnumAdapters(IntPtr self,uint i,out IntPtr adapter);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int GetDesc(IntPtr self,out Adapter desc);
    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
    struct Adapter {
        [MarshalAs(UnmanagedType.ByValTStr,SizeConst=128)] public string Name;
        public uint Vendor,Device,Subsystem,Revision;
        public UIntPtr Dedicated, System, Shared;
        public long Luid;
    }
    static Delegate Slot(IntPtr obj,int index,Type t){return Marshal.GetDelegateForFunctionPointer(Marshal.ReadIntPtr(Marshal.ReadIntPtr(obj),index*IntPtr.Size),t);}
    public static void Check(){
        const string requirements="FORGE requires 64-bit Windows, an AMD CPU, 32 GB installed RAM and an AMD GPU with 16 GB dedicated VRAM.";
        ulong kb;
        string cpu=(string)Registry.GetValue(@"HKEY_LOCAL_MACHINE\HARDWARE\DESCRIPTION\System\CentralProcessor\0","VendorIdentifier","");
        if(!Environment.Is64BitProcess||cpu!="AuthenticAMD")throw new Exception(requirements+" Detected CPU vendor: "+cpu);
        if(!GetPhysicallyInstalledSystemMemory(out kb)||kb<32UL*1024*1024)throw new Exception(requirements+" Installed RAM reported: "+kb/1048576.0+" GB.");
        var id=new Guid("770aae78-f26f-4dba-a829-253c83d1b387");IntPtr factory;
        Marshal.ThrowExceptionForHR(CreateDXGIFactory1(ref id,out factory));
        string adapters="";
        try{
            var next=(EnumAdapters)Slot(factory,7,typeof(EnumAdapters));
            for(uint i=0;;i++){IntPtr adapter;if(next(factory,i,out adapter)!=0)break;
                try{Adapter gpu;var desc=(GetDesc)Slot(adapter,8,typeof(GetDesc));
                    if(desc(adapter,out gpu)==0){double gb=gpu.Dedicated.ToUInt64()/1073741824.0;adapters+=gpu.Name+" ("+gb.ToString("F2")+" GB) ";if(gpu.Vendor==0x1002&&gb>=15.75)return;}
                }finally{Marshal.Release(adapter);}
            }
        }finally{Marshal.Release(factory);}
        throw new Exception(requirements+" Detected adapters: "+adapters);
    }
}

internal static class Setup {
    public static void Install(string app){
        Hardware.Check();
        using(var process=Process.Start(new ProcessStartInfo("powershell.exe","-NoProfile -ExecutionPolicy Bypass -File "+Forge.Quote(Path.Combine(app,"setup-runtime.ps1"))){UseShellExecute=true})){
            process.WaitForExit();if(process.ExitCode!=0)throw new Exception("Setup stopped. Open FORGE to retry. See setup.log in %LOCALAPPDATA%\\FORGE-Data.");
        }
    }
    public static void Remove(){
        string dir=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"FORGE-Data","runtime");
        if(File.Exists(Path.Combine(dir,".forge-owned")))RemoveTree(new DirectoryInfo(dir));
    }
    static void RemoveTree(DirectoryInfo dir){
        if((dir.Attributes & FileAttributes.ReparsePoint)==0){
            foreach(FileInfo file in dir.GetFiles()){if((file.Attributes & FileAttributes.ReparsePoint)==0)file.IsReadOnly=false;file.Delete();}
            foreach(DirectoryInfo child in dir.GetDirectories())RemoveTree(child);
        }
        dir.Delete();
    }
}
