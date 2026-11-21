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
    readonly Queue<string> inputs=new Queue<string>();
    readonly List<Dictionary<string,string>> conversation=new List<Dictionary<string,string>>();
    string attachment;
    string lastSubject;
    readonly Dictionary<string,string> config;
    readonly string configPath;
    readonly Brush ink, paper, card, accent;
    bool busy;
    int total, finished, failed;
    DateTime started;
    static Brush Paint(string hex){return (Brush)new BrushConverter().ConvertFromString(hex);}
    TextBlock Label(string value,double size){return new TextBlock{Text=value,FontSize=size,Foreground=ink,TextWrapping=TextWrapping.Wrap};}
    // Design tokens: quiet hairlines and tonal fills instead of accent outlines.
    Brush line, wash, washHover, muted, onAccent, accentSoft, danger;
    const string Glyphs="Segoe MDL2 Assets";
    readonly Border composerCard=new Border();
    readonly WrapPanel attachmentTray=new WrapPanel();
    // Tonal (secondary) or filled (primary) button with a rounded, borderless template.
    Button Button(string text,Action action){return Button(text,action,false);}
    Button Button(string text,Action action,bool primary){
        var b=new Button{Content=text,Padding=new Thickness(14,7,14,7),Margin=new Thickness(3),Cursor=Cursors.Hand,FontSize=13.5,
                         Background=primary?accent:wash,Foreground=primary?onAccent:ink,BorderBrush=Brushes.Transparent,BorderThickness=new Thickness(0)};
        Round(b,new CornerRadius(10),primary);
        b.Click+=(s,e)=>action();return b;
    }
    Button IconButton(string glyph,string name,Action action,bool primary,double size){
        var b=new Button{Content=new TextBlock{Text=glyph,FontFamily=new FontFamily(Glyphs),FontSize=size*.4,HorizontalAlignment=HorizontalAlignment.Center,VerticalAlignment=VerticalAlignment.Center},
                         Width=size,Height=size,Padding=new Thickness(0),Cursor=Cursors.Hand,ToolTip=name,
                         Background=primary?accent:Brushes.Transparent,Foreground=primary?onAccent:ink,BorderThickness=new Thickness(0),VerticalAlignment=VerticalAlignment.Bottom};
        System.Windows.Automation.AutomationProperties.SetName(b,name);
        Round(b,new CornerRadius(size/2),primary);
        b.Click+=(s,e)=>action();return b;
    }
    void Round(Button b,CornerRadius radius,bool primary){
        if(SystemParameters.HighContrast){b.BorderThickness=new Thickness(1);b.BorderBrush=SystemColors.WindowTextBrush;return;}
        var border=new FrameworkElementFactory(typeof(Border));
        border.SetValue(Border.CornerRadiusProperty,radius);
        foreach(var prop in new[]{Border.BackgroundProperty,Border.BorderBrushProperty,Border.BorderThicknessProperty,Border.PaddingProperty})
            border.SetBinding(prop,new System.Windows.Data.Binding(prop.Name){RelativeSource=System.Windows.Data.RelativeSource.TemplatedParent});
        var label=new FrameworkElementFactory(typeof(ContentPresenter));
        label.SetValue(HorizontalAlignmentProperty,HorizontalAlignment.Center);
        label.SetValue(VerticalAlignmentProperty,VerticalAlignment.Center);
        border.AppendChild(label);
        var template=new ControlTemplate(typeof(Button)){VisualTree=border};
        var pressed=new Trigger{Property=System.Windows.Controls.Primitives.ButtonBase.IsPressedProperty,Value=true};
        pressed.Setters.Add(new Setter(UIElement.OpacityProperty,.72));template.Triggers.Add(pressed);
        var disabled=new Trigger{Property=UIElement.IsEnabledProperty,Value=false};
        disabled.Setters.Add(new Setter(UIElement.OpacityProperty,.4));template.Triggers.Add(disabled);
        b.Template=template;
        Brush rest=b.Background;
        b.MouseEnter+=(s,e)=>{if(primary)b.Opacity=.9;else b.Background=washHover;};
        b.MouseLeave+=(s,e)=>{if(primary)b.Opacity=1;else b.Background=rest;};
    }
    static readonly string[] Attachable={".png",".jpg",".jpeg",".webp",".glb",".fbx"};
    // The attachment lives inside the composer as a chip; its hover "x" is the only way to clear it.
    void SetAttachment(string path){
        attachment=path;attachmentTray.Children.Clear();
        attachmentTray.Visibility=path==null?Visibility.Collapsed:Visibility.Visible;
        if(path!=null)attachmentTray.Children.Add(AttachmentChip(path));
    }
    FrameworkElement AttachmentChip(string path){
        string ext=Path.GetExtension(path).ToLowerInvariant();bool model=ext==".glb"||ext==".fbx";
        FrameworkElement thumb=null;
        if(!model){try{var img=new Image{Source=Preview.Picture(path),Width=40,Height=40,Stretch=Stretch.UniformToFill};img.Clip=new RectangleGeometry(new Rect(0,0,40,40),8,8);thumb=img;}catch(Exception){}}
        if(thumb==null)thumb=new Border{Width=40,Height=40,CornerRadius=new CornerRadius(8),Background=accentSoft,
            Child=new TextBlock{Text=model?"3D":ext.TrimStart('.').ToUpperInvariant(),FontWeight=FontWeights.Bold,FontSize=13,Foreground=accent,HorizontalAlignment=HorizontalAlignment.Center,VerticalAlignment=VerticalAlignment.Center}};
        var text=new StackPanel{Margin=new Thickness(10,0,0,0),VerticalAlignment=VerticalAlignment.Center};
        text.Children.Add(new TextBlock{Text=Path.GetFileName(path),FontSize=13,FontWeight=FontWeights.SemiBold,Foreground=ink,MaxWidth=240,TextTrimming=TextTrimming.CharacterEllipsis});
        text.Children.Add(new TextBlock{Text=(model?"3D model":"Image")+" \u00B7 "+ext.TrimStart('.').ToUpperInvariant(),FontSize=12,Foreground=muted});
        var content=new StackPanel{Orientation=Orientation.Horizontal};content.Children.Add(thumb);content.Children.Add(text);
        var chip=new Border{CornerRadius=new CornerRadius(12),Background=wash,Padding=new Thickness(6,6,14,6),Margin=new Thickness(0,8,8,0),Child=content,ToolTip=path};
        var close=new Button{Content=new TextBlock{Text="\uE711",FontFamily=new FontFamily(Glyphs),FontSize=8,FontWeight=FontWeights.Bold,HorizontalAlignment=HorizontalAlignment.Center,VerticalAlignment=VerticalAlignment.Center},
                             Width=20,Height=20,Padding=new Thickness(0),Background=danger,Foreground=Brushes.White,BorderBrush=card,BorderThickness=new Thickness(2),
                             Cursor=Cursors.Hand,ToolTip="Clear attachment",HorizontalAlignment=HorizontalAlignment.Right,VerticalAlignment=VerticalAlignment.Top,Opacity=0};
        System.Windows.Automation.AutomationProperties.SetName(close,"Clear attachment");
        Round(close,new CornerRadius(10),true);
        close.Click+=(s,e)=>{SetAttachment(null);composer.Focus();};
        var host=new Grid();host.Children.Add(chip);host.Children.Add(close);
        Action<double> fade=to=>close.BeginAnimation(UIElement.OpacityProperty,new System.Windows.Media.Animation.DoubleAnimation(to,TimeSpan.FromMilliseconds(140)));
        host.MouseEnter+=(s,e)=>fade(1);host.MouseLeave+=(s,e)=>{if(!close.IsKeyboardFocused)fade(0);};
        close.GotKeyboardFocus+=(s,e)=>fade(1);close.LostKeyboardFocus+=(s,e)=>{if(!host.IsMouseOver)fade(0);};
        return host;
    }
    public Forge(string configFile) {
        configPath=configFile;
        if(File.Exists(configFile))config=new JavaScriptSerializer().Deserialize<Dictionary<string,string>>(File.ReadAllText(configFile));
        bool dark=Convert.ToInt32(Registry.GetValue(@"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize","AppsUseLightTheme",1))==0;
        ink=SystemParameters.HighContrast?SystemColors.WindowTextBrush:Paint(dark?"#EDF1F5":"#192838");
        paper=SystemParameters.HighContrast?SystemColors.WindowBrush:Paint(dark?"#161B20":"#F2F5F8");
        card=SystemParameters.HighContrast?SystemColors.WindowBrush:Paint(dark?"#232B33":"#FFFFFF");
        accent=SystemParameters.HighContrast?SystemColors.HighlightBrush:Paint(dark?"#80DCCC":"#13685F");
        bool hc=SystemParameters.HighContrast;
        line=hc?SystemColors.WindowTextBrush:Paint(dark?"#24FFFFFF":"#1F192838");
        wash=hc?SystemColors.ControlBrush:Paint(dark?"#14FFFFFF":"#0B192838");
        washHover=hc?SystemColors.ControlLightBrush:Paint(dark?"#24FFFFFF":"#16192838");
        muted=hc?SystemColors.GrayTextBrush:Paint(dark?"#9AA7B4":"#5E6B78");
        onAccent=hc?SystemColors.HighlightTextBrush:(dark?Brushes.Black:Brushes.White);
        accentSoft=hc?SystemColors.ControlBrush:Paint(dark?"#2680DCCC":"#1A13685F");
        danger=hc?SystemColors.HighlightBrush:Paint("#E5484D");
        Icon=AppIcon();Title="FORGE v0.04";Width=980;Height=810;MinWidth=720;MinHeight=520;Background=paper;Foreground=ink;
        FontFamily=new FontFamily("Segoe UI");WindowStartupLocation=WindowStartupLocation.CenterScreen;
        var root=new DockPanel();Content=new Border{Padding=new Thickness(26,16,26,16),Background=paper,Child=root};
        var header=new DockPanel{Margin=new Thickness(0,0,0,12)};
        var open=Button("Open model",()=>{var dlg=new OpenFileDialog{Filter="Models|*.glb;*.fbx"};if(dlg.ShowDialog()==true){SetAttachment(dlg.FileName);if(Path.GetExtension(attachment).ToLowerInvariant()==".glb")AddModel(attachment);else AddText("FBX selected. Type rig to rig this model.",15);}});
        DockPanel.SetDock(open,Dock.Right);header.Children.Add(open);var brand=Label("FORGE",24);brand.FontWeight=FontWeights.Bold;header.Children.Add(brand);
        DockPanel.SetDock(header,Dock.Top);root.Children.Add(header);
        var footer=new StackPanel{Margin=new Thickness(0,12,0,0)};DockPanel.SetDock(footer,Dock.Bottom);root.Children.Add(footer);
        status.Text="Ready";status.Foreground=muted;status.FontSize=12.5;status.Margin=new Thickness(4,0,0,0);footer.Children.Add(status);
        progress.Height=3;progress.Margin=new Thickness(4,6,4,10);progress.BorderThickness=new Thickness(0);progress.Background=wash;progress.Foreground=accent;footer.Children.Add(progress);
        // Composer: one rounded, softly elevated surface holding the attachment chip, field and actions.
        var stack=new StackPanel();
        attachmentTray.Margin=new Thickness(8,2,8,4);attachmentTray.Visibility=Visibility.Collapsed;stack.Children.Add(attachmentTray);
        var row=new DockPanel();
        var send=IconButton("\uE74A","Send",Submit,true,38);DockPanel.SetDock(send,Dock.Right);row.Children.Add(send);
        var attach=IconButton("\uE710","Attach an image or model",()=>{var dlg=new OpenFileDialog{Filter="Images and models|*.png;*.jpg;*.jpeg;*.webp;*.glb;*.fbx"};if(dlg.ShowDialog()==true)SetAttachment(dlg.FileName);composer.Focus();},false,38);
        attach.Background=wash;attach.MouseLeave+=(s,e)=>attach.Background=wash;DockPanel.SetDock(attach,Dock.Left);row.Children.Add(attach);
        composer.Padding=new Thickness(10,8,10,8);composer.FontSize=15.5;composer.Background=Brushes.Transparent;composer.Foreground=ink;composer.CaretBrush=ink;
        composer.BorderThickness=new Thickness(0);composer.VerticalContentAlignment=VerticalAlignment.Center;composer.TextWrapping=TextWrapping.Wrap;composer.MaxHeight=140;
        composer.VerticalScrollBarVisibility=ScrollBarVisibility.Auto;composer.FocusVisualStyle=null;
        System.Windows.Automation.AutomationProperties.SetName(composer,"Message");
        composer.KeyDown+=(s,e)=>{if(e.Key==Key.Enter&&(Keyboard.Modifiers&ModifierKeys.Shift)==0){Submit();e.Handled=true;}};
        var placeholder=new TextBlock{Text="Describe something to forge, or ask anything",FontSize=15.5,Foreground=muted,Margin=new Thickness(13,0,10,0),VerticalAlignment=VerticalAlignment.Center,IsHitTestVisible=false};
        composer.TextChanged+=(s,e)=>placeholder.Visibility=composer.Text.Length==0?Visibility.Visible:Visibility.Collapsed;
        var field=new Grid{Margin=new Thickness(4,0,4,0)};field.Children.Add(composer);field.Children.Add(placeholder);row.Children.Add(field);
        stack.Children.Add(row);
        composerCard.Child=stack;composerCard.CornerRadius=new CornerRadius(24);composerCard.Background=card;composerCard.Padding=new Thickness(6);
        composerCard.BorderBrush=line;composerCard.BorderThickness=new Thickness(1);
        if(!hc)composerCard.Effect=new System.Windows.Media.Effects.DropShadowEffect{BlurRadius=24,ShadowDepth=3,Direction=270,Opacity=dark?.45:.10,Color=Colors.Black};
        composer.GotKeyboardFocus+=(s,e)=>composerCard.BorderBrush=accent;
        composer.LostKeyboardFocus+=(s,e)=>composerCard.BorderBrush=line;
        footer.Children.Add(composerCard);
        // Dropping an image or model anywhere on the window attaches it.
        AllowDrop=true;
        DragOver+=(s,e)=>{var files=e.Data.GetData(DataFormats.FileDrop) as string[];e.Effects=files!=null&&files.Any(f=>Attachable.Contains(Path.GetExtension(f).ToLowerInvariant()))?DragDropEffects.Copy:DragDropEffects.None;e.Handled=true;};
        Drop+=(s,e)=>{var files=e.Data.GetData(DataFormats.FileDrop) as string[];if(files==null)return;var hit=files.FirstOrDefault(f=>Attachable.Contains(Path.GetExtension(f).ToLowerInvariant()));if(hit!=null){SetAttachment(hit);composer.Focus();}};
        details.IsReadOnly=true;details.VerticalScrollBarVisibility=ScrollBarVisibility.Auto;details.Height=90;
        details.Background=wash;details.Foreground=ink;details.BorderThickness=new Thickness(0);details.Padding=new Thickness(8);details.FontFamily=new FontFamily("Cascadia Mono, Consolas");details.FontSize=12;
        footer.Children.Add(new Expander{Header="Build log",Content=details,Foreground=muted,Margin=new Thickness(4,10,0,0)});
        history.VerticalScrollBarVisibility=ScrollBarVisibility.Auto;history.Content=cards;root.Children.Add(history);
        AddText("What would you like to build?",20);
        var heartbeat=new System.Windows.Threading.DispatcherTimer{Interval=TimeSpan.FromSeconds(1)};
        heartbeat.Tick+=(s,e)=>{if(busy)RefreshStatus();};heartbeat.Start();
        Loaded+=(s,e)=>composer.Focus();
        Closing+=(s,e)=>{if(busy){e.Cancel=true;status.Text="A build is active. Close FORGE after the queue finishes."; }};
    }
    void AddText(string text,double size){var label=Label(text,size);label.Margin=new Thickness(4,10,4,8);cards.Children.Add(label);history.ScrollToEnd();}
    // forge.ico is embedded by packaging/build.py; the window falls back to the default icon without it.
    static ImageSource AppIcon(){
        try{
            var stream=System.Reflection.Assembly.GetExecutingAssembly().GetManifestResourceStream("forge.ico");
            return stream==null?null:BitmapFrame.Create(stream,BitmapCreateOptions.None,BitmapCacheOption.OnLoad);
        }catch(Exception){return null;}
    }
    public void AddModel(string path){
        try {
            var view=new Preview(path);
            view.SetBinding(HeightProperty,new System.Windows.Data.Binding("ViewportHeight"){Source=history});
            var panel=new StackPanel();string stem=Path.GetFileNameWithoutExtension(path);
            string caption=System.Text.RegularExpressions.Regex.Replace(stem,@"_\d{8}_\d{6}_\d+$","");
            var name=Label(caption=="forge"||caption=="simulation"?"Model preview":caption,17);
            name.ToolTip=path;name.FontWeight=FontWeights.SemiBold;
            name.Margin=new Thickness(0,0,0,10);panel.Children.Add(name);panel.Children.Add(view);
            var tools=new DockPanel{Margin=new Thickness(0,8,0,0)};
            var controls=new WrapPanel();
            controls.Children.Add(Button("Rig",()=>{attachment=path;composer.Text="rig it";Submit();}));
            controls.Children.Add(Button("Save",()=>SaveAsset(path)));
            controls.Children.Add(Button("Select",()=>{SetAttachment(path);composer.Focus();}));
            controls.Children.Add(Button("Expand",()=>{var full=new Window{Title=Path.GetFileName(path),Owner=this,Icon=Icon,Width=ActualWidth,Height=ActualHeight};var preview=new Preview(path);preview.Height=Double.NaN;full.Content=preview;full.Show();}));
            controls.Children.Add(Button("Zoom out",()=>view.Zoom(1.2)));controls.Children.Add(Button("Zoom in",()=>view.Zoom(.83)));controls.Children.Add(Button("Reset",view.Reset));
            tools.Children.Add(controls);
            panel.Children.Add(tools);cards.Children.Add(new Border{Child=panel,Background=card,Padding=new Thickness(16),CornerRadius=new CornerRadius(12),Margin=new Thickness(0,8,8,8)});
            history.UpdateLayout();history.ScrollToEnd();
        }catch(Exception ex){AddText("Preview unavailable. "+ex.GetBaseException().Message,15);}
    }
    void SaveAsset(string path){
        var dlg=new SaveFileDialog{FileName=Path.GetFileName(path),Filter="Asset (*"+Path.GetExtension(path)+")|*"+Path.GetExtension(path)};
        if(dlg.ShowDialog()!=true)return;
        try{if(!String.Equals(Path.GetFullPath(path),Path.GetFullPath(dlg.FileName),StringComparison.OrdinalIgnoreCase))File.Copy(path,dlg.FileName,true);}
        catch(Exception ex){AddText("Could not save. "+ex.Message,15);}
    }
    void AddImage(string path){
        var panel=new StackPanel();panel.Children.Add(new Image{Source=Preview.Picture(path),Height=300});
        panel.Children.Add(Button("Save image",()=>SaveAsset(path)));
        panel.Children.Add(Button("Select image",()=>{SetAttachment(path);composer.Focus();}));
        cards.Children.Add(panel);
    }
    async Task Chat(string raw,string source,string job){
        conversation.Add(new Dictionary<string,string>{{"role","user"},{"content",raw}});
        string request=Path.Combine(job,"chat.json"),reply=Path.Combine(job,"reply.txt");
        File.WriteAllText(request,new JavaScriptSerializer().Serialize(new {messages=conversation,attachment=source==null?"none":Path.GetFileName(source)}));
        var info=new ProcessStartInfo(config["python"],Quote(Path.Combine(AppDir,"chat.py"))+" "+Quote(request)+" "+Quote(configPath)+" "+Quote(reply)){UseShellExecute=false,CreateNoWindow=true,RedirectStandardError=true};
        using(var process=Process.Start(info)){
            string errors=await process.StandardError.ReadToEndAsync();
            await Task.Run(()=>process.WaitForExit());
            if(process.ExitCode!=0)throw new Exception("Chat failed. "+errors);
        }
        string response=File.ReadAllText(reply);AddText(response,15);
        conversation.Add(new Dictionary<string,string>{{"role","assistant"},{"content",response}});
        if(conversation.Count>12)conversation.RemoveRange(0,conversation.Count-12);
        var choices=new WrapPanel();
        choices.Children.Add(Button("Generate image",()=>{composer.Text="generate "+raw;Submit();}));
        choices.Children.Add(Button("Build 3D",()=>{composer.Text="forge "+raw;Submit();}));
        cards.Children.Add(choices);
    }
    void Submit(){string raw=composer.Text.Trim();if(raw=="")return;
        string mode=Intent.Mode(raw);
        if(mode=="chat")lastSubject=raw;
        if(attachment==null&&lastSubject!=null&&(mode=="model"||mode=="image")&&System.Text.RegularExpressions.Regex.IsMatch(raw,@"\b(it|that|this)\s*[.!?]*$",System.Text.RegularExpressions.RegexOptions.IgnoreCase))raw=(mode=="model"?"forge ":"generate ")+lastSubject;
        if((mode=="model"||mode=="image")&&attachment==null&&System.Text.RegularExpressions.Regex.IsMatch(raw,@"^(forge|build|make|mold|generate|create|imagine|image)\s*[.!?]*$",System.Text.RegularExpressions.RegexOptions.IgnoreCase)){AddText("What would you like me to create?",15);return;}
        if((mode=="rig"||mode=="background"||mode=="upscale")&&attachment==null){AddText("Attach or select a file for this action.",15);return;}
        if(attachment!=null&&mode!="rig"&&mode!="chat"&&(Path.GetExtension(attachment).ToLowerInvariant()==".fbx"||Path.GetExtension(attachment).ToLowerInvariant()==".glb")){AddText("Select an image for this action, or use rig for the selected model.",15);return;}
        if(attachment!=null&&mode=="image"){AddText("To use the attached image, choose forge or upscale. Clear it to generate a new image.",15);return;}
        if(config==null){AddText("Finish runtime setup and reopen FORGE to build.",15);return;}
        if(mode=="chat"&&!config.ContainsKey("chat")){AddText("Chat is still installing. Reopen FORGE to finish setup, or start with forge or generate.",15);return;}
        if(mode=="rig"&&!config.ContainsKey("unirig")){AddText("Rigging is still installing. Reopen FORGE to finish setup.",15);return;}
        composer.Clear();if(!busy){finished=0;total=0;failed=0;}pending.Enqueue(raw);total++;
        inputs.Enqueue(attachment);if(mode!="chat")SetAttachment(null);
        AddText(raw,17);RefreshStatus();if(!busy)Drain();
    }
    string stage="Starting";
    void RefreshStatus(){status.Text=String.Format("Job {0} of {1}   /   {2} waiting   /   {3}   /   {4:mm\\:ss}",finished+1,total,pending.Count,stage,busy?DateTime.Now-started:TimeSpan.Zero);}
    async void Drain(){busy=true;progress.IsIndeterminate=true;
        while(pending.Count>0){
            string raw=pending.Dequeue();started=DateTime.Now;stage="Starting";RefreshStatus();
            string source=inputs.Dequeue();
            try{
                string mode=Intent.Mode(raw);
                bool image=mode=="image"||mode=="upscale"||mode=="background";
                var named=System.Text.RegularExpressions.Regex.Match(raw,@"\bnamed\s+([a-zA-Z0-9_-]{1,48})",System.Text.RegularExpressions.RegexOptions.IgnoreCase);
                string id=(named.Success?named.Groups[1].Value:image?"image":"forge")+"_"+DateTime.Now.ToString("yyyyMMdd_HHmmss_fffffff");
                if(mode=="chat"){
                    // Chat turns are transient; keep them out of the Documents\FORGE job history.
                    string scratch=Path.Combine(Path.GetTempPath(),"FORGE-chat-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(scratch);
                    stage="Thinking";RefreshStatus();
                    try{await Chat(raw,source,scratch);}finally{try{Directory.Delete(scratch,true);}catch(IOException){}}
                    finished++;continue;
                }
                string job=Path.Combine(config["output"],id);Directory.CreateDirectory(job);File.WriteAllText(Path.Combine(job,"prompt.txt"),raw);
                string log=Path.Combine(job,"pipeline.log");details.Clear();
                string inputArgument="";
                if(source!=null){string copy=Path.Combine(job,"input"+Path.GetExtension(source));File.Copy(source,copy);inputArgument=" --input "+Quote(copy);}
                string asset=Path.Combine(job,id+(image?".png":mode=="rig"?".fbx":".glb"));
                bool previewShown=false;
                var info=new ProcessStartInfo(config["python"],"-u "+Quote(Path.Combine(AppDir,"runner.py"))+" --config "+Quote(configPath)+" --job "+Quote(job)+" --mode "+mode+inputArgument){
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
                if(mode=="rig"){AddText("Rigged model ready",17);cards.Children.Add(Button("Save rigged FBX",()=>SaveAsset(asset)));}
                else if(image)AddImage(asset);
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
            if(args.Contains("--preserve-runtime")){Setup.PreserveRuntime();return 0;}
            if(args.Contains("--restore-runtime")){Setup.RestoreRuntime();return 0;}
            Setup.RestoreRuntime();
            string dev=Path.Combine(AppDir,"development.json");
            string cfg=File.Exists(dev)?dev:Path.Combine(Data,"runtime","config.json");
            if(!File.Exists(dev)&&!Setup.Ready(AppDir)&&args.Length==0){
                try{Setup.Install(AppDir);}
                catch(Exception ex){
                    // The core runtime still works when only the v0.04 chat/UniRig step failed.
                    if(!File.Exists(cfg))throw;
                    MessageBox.Show(ex.GetBaseException().Message+"\n\nImage and 3D generation are available. Chat and rigging finish installing the next time FORGE opens.","FORGE");
                }
            }
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
