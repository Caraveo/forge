using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Web.Script.Serialization;
using Microsoft.Win32;

internal sealed class Forge : Window {
    static readonly string AppDir = AppDomain.CurrentDomain.BaseDirectory;
    static readonly string Data = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"FORGE-Data");
    readonly StackPanel cards=new StackPanel();
    readonly ScrollViewer history=new ScrollViewer();
    readonly TextBox composer=new TextBox(), details=new TextBox();
    readonly TextBlock status=new TextBlock();
    readonly ProgressBar progress=new ProgressBar();
    readonly Queue<string> pending=new Queue<string>();
    readonly Dictionary<string,string> config;
    readonly string configPath;
    readonly Brush ink, paper, card, accent;
    bool busy;
    int total, finished, failed;
    DateTime started;
    static Brush Paint(string hex){return (Brush)new BrushConverter().ConvertFromString(hex);}
    TextBlock Label(string value,double size){return new TextBlock{Text=value,FontSize=size,Foreground=ink,TextWrapping=TextWrapping.Wrap};}
    Button Button(string text,Action action){
        var b=new Button{Content=text,Padding=new Thickness(14,7,14,7),Margin=new Thickness(3),Cursor=Cursors.Hand,
                         Background=card,Foreground=ink,BorderBrush=accent,BorderThickness=new Thickness(1)};
        if(!SystemParameters.HighContrast){
            var border=new FrameworkElementFactory(typeof(Border));
            border.SetValue(Border.CornerRadiusProperty,new CornerRadius(8));
            foreach(var prop in new[]{Border.BackgroundProperty,Border.BorderBrushProperty,Border.BorderThicknessProperty,Border.PaddingProperty})
                border.SetBinding(prop,new System.Windows.Data.Binding(prop.Name){RelativeSource=System.Windows.Data.RelativeSource.TemplatedParent});
            var label=new FrameworkElementFactory(typeof(ContentPresenter));
            label.SetValue(HorizontalAlignmentProperty,HorizontalAlignment.Center);
            label.SetValue(VerticalAlignmentProperty,VerticalAlignment.Center);
            border.AppendChild(label);
            var template=new ControlTemplate(typeof(Button)){VisualTree=border};
            var over=new Trigger{Property=UIElement.IsMouseOverProperty,Value=true};
            over.Setters.Add(new Setter(UIElement.OpacityProperty,.8));template.Triggers.Add(over);b.Template=template;
        }
        b.Click+=(s,e)=>action();return b;
    }
    public Forge(string configFile) {
        configPath=configFile;
        if(File.Exists(configFile))config=new JavaScriptSerializer().Deserialize<Dictionary<string,string>>(File.ReadAllText(configFile));
        bool dark=Convert.ToInt32(Registry.GetValue(@"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize","AppsUseLightTheme",1))==0;
        ink=SystemParameters.HighContrast?SystemColors.WindowTextBrush:Paint(dark?"#EDF1F5":"#192838");
        paper=SystemParameters.HighContrast?SystemColors.WindowBrush:Paint(dark?"#161B20":"#F2F5F8");
        card=SystemParameters.HighContrast?SystemColors.WindowBrush:Paint(dark?"#232B33":"#FFFFFF");
        accent=SystemParameters.HighContrast?SystemColors.HighlightBrush:Paint(dark?"#80DCCC":"#13685F");
        Title="FORGE";Width=980;Height=810;MinWidth=560;MinHeight=520;Background=paper;Foreground=ink;
        FontFamily=new FontFamily("Segoe UI");WindowStartupLocation=WindowStartupLocation.CenterScreen;
        var root=new DockPanel();Content=new Border{Padding=new Thickness(26,16,26,16),Background=paper,Child=root};
        var header=new DockPanel{Margin=new Thickness(0,0,0,12)};
        var open=Button("Open model",()=>{var dlg=new OpenFileDialog{Filter="FORGE model (*.glb)|*.glb"};if(dlg.ShowDialog()==true)AddModel(dlg.FileName);});
        DockPanel.SetDock(open,Dock.Right);header.Children.Add(open);var brand=Label("FORGE",24);brand.FontWeight=FontWeights.Bold;header.Children.Add(brand);
        DockPanel.SetDock(header,Dock.Top);root.Children.Add(header);
        var footer=new StackPanel{Margin=new Thickness(0,12,0,0)};DockPanel.SetDock(footer,Dock.Bottom);root.Children.Add(footer);
        status.Text="Ready";status.Foreground=ink;footer.Children.Add(status);
        progress.Height=4;progress.Margin=new Thickness(0,5,0,8);footer.Children.Add(progress);
        var row=new DockPanel();var send=Button("Build",Submit);send.Background=accent;send.Foreground=dark?Brushes.Black:Brushes.White;send.MinWidth=90;DockPanel.SetDock(send,Dock.Right);row.Children.Add(send);
        composer.Padding=new Thickness(12,9,12,9);composer.FontSize=16;composer.Background=card;composer.Foreground=ink;
        composer.ToolTip="Describe a model, or type generate for an image";composer.KeyDown+=(s,e)=>{if(e.Key==Key.Enter){Submit();e.Handled=true;}};
        row.Children.Add(composer);footer.Children.Add(row);
        details.IsReadOnly=true;details.VerticalScrollBarVisibility=ScrollBarVisibility.Auto;details.Height=90;
        footer.Children.Add(new Expander{Header="Build log",Content=details,Foreground=ink,Margin=new Thickness(0,6,0,0)});
        history.VerticalScrollBarVisibility=ScrollBarVisibility.Auto;history.Content=cards;root.Children.Add(history);
        AddText("What would you like to build?",20);
        var heartbeat=new System.Windows.Threading.DispatcherTimer{Interval=TimeSpan.FromSeconds(1)};
        heartbeat.Tick+=(s,e)=>{if(busy)RefreshStatus();};heartbeat.Start();
        Loaded+=(s,e)=>composer.Focus();
        Closing+=(s,e)=>{if(busy){e.Cancel=true;status.Text="A build is active. Close FORGE after the queue finishes."; }};
    }
    void AddText(string text,double size){var label=Label(text,size);label.Margin=new Thickness(4,10,4,8);cards.Children.Add(label);history.ScrollToEnd();}
    public void AddModel(string path){
        try {
            var view=new Preview(path);
            var panel=new StackPanel();string stem=Path.GetFileNameWithoutExtension(path);
            string caption=System.Text.RegularExpressions.Regex.Replace(stem,@"_\d{8}_\d{6}_\d+$","");
            var name=Label(caption=="forge"||caption=="simulation"?"Model preview":caption,17);
            name.ToolTip=path;name.FontWeight=FontWeights.SemiBold;
            name.Margin=new Thickness(0,0,0,10);panel.Children.Add(name);panel.Children.Add(view);
            var tools=new DockPanel{Margin=new Thickness(0,8,0,0)};
            var controls=new StackPanel{Orientation=Orientation.Horizontal};
            controls.Children.Add(Button("Zoom out",()=>view.Zoom(1.2)));controls.Children.Add(Button("Zoom in",()=>view.Zoom(.83)));controls.Children.Add(Button("Reset",view.Reset));
            DockPanel.SetDock(controls,Dock.Right);tools.Children.Add(controls);var hint=Label("Drag to rotate   /   Ctrl + wheel to zoom",13);hint.VerticalAlignment=VerticalAlignment.Center;tools.Children.Add(hint);
            panel.Children.Add(tools);cards.Children.Add(new Border{Child=panel,Background=card,Padding=new Thickness(16),CornerRadius=new CornerRadius(12),Margin=new Thickness(0,8,8,8)});
            history.UpdateLayout();history.ScrollToEnd();
        }catch(Exception ex){AddText("Preview unavailable. "+ex.GetBaseException().Message,15);}
    }
    void Submit(){string raw=composer.Text.Trim();if(raw=="")return;
        if(config==null){AddText("Finish runtime setup and reopen FORGE to build.",15);return;}
        composer.Clear();if(!busy){finished=0;total=0;failed=0;}pending.Enqueue(raw);total++;
        AddText(raw,17);RefreshStatus();if(!busy)Drain();
    }
    string stage="Starting";
    void RefreshStatus(){status.Text=String.Format("Job {0} of {1}   /   {2} waiting   /   {3}   /   {4:mm\\:ss}",finished+1,total,pending.Count,stage,busy?DateTime.Now-started:TimeSpan.Zero);}
    async void Drain(){busy=true;progress.IsIndeterminate=true;
        while(pending.Count>0){
            string raw=pending.Dequeue();started=DateTime.Now;stage="Starting";RefreshStatus();
            try{
                bool image=System.Text.RegularExpressions.Regex.IsMatch(raw,@"^(generate|image)\b",System.Text.RegularExpressions.RegexOptions.IgnoreCase);
                var named=System.Text.RegularExpressions.Regex.Match(raw,@"\bnamed\s+([a-zA-Z0-9_-]{1,48})",System.Text.RegularExpressions.RegexOptions.IgnoreCase);
                string id=(named.Success?named.Groups[1].Value:image?"image":"forge")+"_"+DateTime.Now.ToString("yyyyMMdd_HHmmss_fffffff");
                string job=Path.Combine(config["output"],id);Directory.CreateDirectory(job);File.WriteAllText(Path.Combine(job,"prompt.txt"),raw);
                string log=Path.Combine(job,"pipeline.log");details.Clear();
                string asset=Path.Combine(job,id+(image?".png":".glb"));
                bool previewShown=false;
                var info=new ProcessStartInfo(config["python"],"-u "+Quote(Path.Combine(AppDir,"runner.py"))+" --config "+Quote(configPath)+" --job "+Quote(job)+" --mode "+(image?"image":"model")){
                    UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true,WorkingDirectory=job};
                using(var writer=File.CreateText(log))using(var proc=new Process{StartInfo=info}){
                    writer.AutoFlush=true;
                    DataReceivedEventHandler line=(s,e)=>{if(e.Data==null)return;lock(writer)writer.WriteLine(e.Data);
                        Dispatcher.BeginInvoke(new Action(()=>{if(e.Data.StartsWith("[stage] ")){stage=e.Data.Substring(8);RefreshStatus();
                            progress.IsIndeterminate=true;
                            if(stage=="Preparing Unity files" && !previewShown && File.Exists(asset)){AddModel(asset);previewShown=true;}}
                            if(e.Data.Contains("[flow]")){
                                var step=System.Text.RegularExpressions.Regex.Match(e.Data,@"\]\s+(\d+)/(\d+).*?~([\d.]+)s left");
                                if(step.Success){int done=int.Parse(step.Groups[1].Value), count=int.Parse(step.Groups[2].Value);
                                    progress.IsIndeterminate=false;progress.Value=100.0*done/Math.Max(1,count);
                                    stage="Building model   /   "+done+" of "+count+" steps   /   ~"+step.Groups[3].Value+"s in this pass";RefreshStatus();}
                            }
                            if(details.Text.Length>40000)details.Text=details.Text.Substring(20000);details.AppendText(e.Data+Environment.NewLine);details.ScrollToEnd();}));};
                    proc.OutputDataReceived+=line;proc.ErrorDataReceived+=line;proc.Start();proc.BeginOutputReadLine();proc.BeginErrorReadLine();
                    await Task.Run(()=>proc.WaitForExit());if(proc.ExitCode!=0)throw new Exception("Build failed. "+log);
                }
                if(image)cards.Children.Add(new Image{Source=Preview.Picture(asset),Height=300});
                else if(!previewShown){AddModel(asset);previewShown=true;}
                AddText("Saved in "+job,13);
            }catch(Exception ex){failed++;AddText(ex.GetBaseException().Message,15);}finished++;
        }
        busy=false;progress.IsIndeterminate=false;progress.Value=100;
        status.Text=String.Format("{0} completed   /   {1} failed",finished-failed,failed);history.ScrollToEnd();
    }
    public static string Quote(string path){return "\""+path+"\"";}
    [STAThread] public static int Main(string[] args){
        try{
            if(args.Contains("--check")){Hardware.Check();return 0;}
            if(args.Contains("--remove-runtime")){Setup.Remove();return 0;}
            string dev=Path.Combine(AppDir,"development.json");
            string cfg=File.Exists(dev)?dev:Path.Combine(Data,"runtime","config.json");
            if(!File.Exists(cfg)&&args.Length==0)Setup.Install(AppDir);
            var app=new Application();var window=new Forge(cfg);
            if(args.Length>=2 && args[0]=="--preview")window.ContentRendered+=(s,e)=>{
                window.AddModel(args[1]);
                if(args.Length>=3){window.UpdateLayout();var size=((FrameworkElement)window.Content).RenderSize;var shot=new RenderTargetBitmap((int)size.Width,(int)size.Height,96,96,PixelFormats.Pbgra32);
                    shot.Render((Visual)window.Content);var enc=new PngBitmapEncoder();enc.Frames.Add(BitmapFrame.Create(shot));using(var stream=File.Create(args[2]))enc.Save(stream);window.Close();}};
            if(args.Length>=2 && args[0]=="--build")window.ContentRendered+=(s,e)=>{window.composer.Text=String.Join(" ",args.Skip(1));window.Submit();};
            app.Run(window);return 0;
        }catch(Exception ex){Console.Error.WriteLine(ex.GetBaseException().Message);if(!args.Contains("--quiet"))MessageBox.Show(ex.GetBaseException().Message,"FORGE");return 1;}
    }
}
