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
    // One queued or running piece of work, shown as a card under the composer.
    sealed class Job {
        public string Raw,Source,Name,Mode,Quality,Folder,Stage="Waiting in line";
        public Border Card;public TextBlock Pill,Detail;public ProgressBar Bar;public Button Action;
        public FrameworkElement Anchor;public Process Proc;public DateTime Started;
        public bool Cancelled,Done,ModelShown;public System.Windows.Threading.DispatcherTimer Watch;
    }
    readonly Queue<Job> pending=new Queue<Job>();
    readonly StackPanel jobList=new StackPanel();
    readonly ScrollViewer jobScroller=new ScrollViewer();
    readonly Expander buildLog=new Expander();
    readonly System.Threading.SemaphoreSlim chatGate=new System.Threading.SemaphoreSlim(1);
    Job current;
    // Off for scripted --build runs, which have nobody to pick a name.
    public bool askNames=true;
    readonly List<Dictionary<string,string>> conversation=new List<Dictionary<string,string>>();
    string attachment;
    string lastSubject;
    readonly Dictionary<string,string> config;
    readonly string configPath;
    readonly Brush ink, paper, card, accent;
    bool busy;
    int failed;
    static Brush Paint(string hex){return (Brush)new BrushConverter().ConvertFromString(hex);}
    TextBlock Label(string value,double size){return new TextBlock{Text=value,FontSize=size,Foreground=ink,TextWrapping=TextWrapping.Wrap};}
    // Design tokens: quiet hairlines and tonal fills instead of accent outlines.
    Brush line, wash, washHover, muted, onAccent, accentSoft, danger;
    const string Glyphs="Segoe MDL2 Assets";
    readonly Border composerCard=new Border();
    readonly WrapPanel attachmentTray=new WrapPanel();
    // Next-step actions for the attachment, shown between the job cards and the composer.
    readonly WrapPanel actionBar=new WrapPanel{Margin=new Thickness(2,0,0,8),Visibility=Visibility.Collapsed};
    // Tonal (secondary) or filled (primary) button with a rounded, borderless template.
    Button Button(string text,Action action,bool primary=false,double radius=10){
        var b=new Button{Content=text,Padding=new Thickness(14,7,14,7),Margin=new Thickness(3),Cursor=Cursors.Hand,FontSize=13.5,
                         Background=primary?accent:wash,Foreground=primary?onAccent:ink,BorderBrush=Brushes.Transparent,BorderThickness=new Thickness(0)};
        Round(b,new CornerRadius(radius),primary);
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
    // Text files are read in as a prompt rather than attached.
    static readonly string[] Accepted=Attachable.Concat(new[]{".txt"}).ToArray();
    const string OpenFilter="Images, 3D models and text prompts|*.png;*.jpg;*.jpeg;*.webp;*.glb;*.fbx;*.txt|Images|*.png;*.jpg;*.jpeg;*.webp|3D models|*.glb;*.fbx|Text prompt|*.txt";
    // The single entry point for files from +, drag-and-drop or anywhere else.
    void AcceptFile(string path){
        string ext=Path.GetExtension(path).ToLowerInvariant();
        if(ext==".txt"){
            try{
                if(new FileInfo(path).Length>65536){AddText("\U0001F4C4 That text file is too large to use as a prompt (64 KB at most).",14);return;}
                string text=File.ReadAllText(path);
                text=System.Text.RegularExpressions.Regex.Replace(text,@"[\u0000-\u001F\u007F]+"," ");
                text=System.Text.RegularExpressions.Regex.Replace(text,@"\s+"," ").Trim();
                if(text.Length==0){AddText("\U0001F4C4 That text file is empty.",14);return;}
                if(text.Length>2000)text=text.Substring(0,2000).TrimEnd();
                // Shown for review; nothing runs until Enter is pressed.
                composer.Text=text;composer.CaretIndex=text.Length;composer.Focus();
            }catch(Exception ex){AddText("\U0001F4C4 Could not read that text file. "+ex.GetBaseException().Message,14);}
            return;
        }
        if(!Attachable.Contains(ext)){
            AddText("\U0001F6AB FORGE can't work with "+(ext.Length>0?ext.ToUpperInvariant().TrimStart('.')+" files":"that file")+". Attach an image (PNG, JPEG, WebP), a 3D model (GLB, FBX) or a text prompt (TXT).",14);
            return;
        }
        SetAttachment(path);composer.Focus();
    }
    // The attachment lives inside the composer as a chip; its hover "x" is the only way to clear it.
    void SetAttachment(string path){
        attachment=path;attachmentTray.Children.Clear();actionBar.Children.Clear();actionBar.Visibility=Visibility.Collapsed;
        attachmentTray.Visibility=path==null?Visibility.Collapsed:Visibility.Visible;
        if(path==null)return;
        attachmentTray.Children.Add(AttachmentChip(path));
        // Suggest what this file can do next, right beside it.
        string ext=Path.GetExtension(path).ToLowerInvariant();
        var actions=new List<Tuple<string,Action>>();
        Action<string> run=command=>{composer.Text=command;Submit();};
        if(ext==".glb")actions.Add(Tuple.Create<string,Action>("\U0001F440 Preview",()=>AddModel(path)));
        if(ext==".glb"||ext==".fbx")actions.Add(Tuple.Create<string,Action>("\U0001F9B4 Rig",()=>run("rig it")));
        else{
            actions.Add(Tuple.Create<string,Action>("\U0001F9F1 Build 3D",()=>run("forge")));
            actions.Add(Tuple.Create<string,Action>("\u2702\uFE0F Remove background",()=>run("remove background")));
            actions.Add(Tuple.Create<string,Action>("\U0001F50D Upscale",()=>run("upscale")));
        }
        foreach(var action in actions){
            var b=Button(action.Item1,action.Item2,false,16);b.FontSize=12.5;b.Padding=new Thickness(12,5,12,5);
            b.Margin=new Thickness(0,0,6,0);actionBar.Children.Add(b);actionBar.Visibility=Visibility.Visible;
        }
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
        Icon=AppIcon();Title="FORGE v0.05";Width=980;Height=810;MinWidth=720;MinHeight=520;Background=paper;Foreground=ink;
        FontFamily=new FontFamily("Segoe UI");WindowStartupLocation=WindowStartupLocation.CenterScreen;
        var root=new DockPanel();Content=new Border{Padding=new Thickness(26,16,26,16),Background=paper,Child=root};
        var header=new DockPanel{Margin=new Thickness(0,0,0,12)};
        // Opening a model happens through + or drag-and-drop; the attachment then offers Preview.
        var brand=Label("FORGE",24);brand.FontWeight=FontWeights.Bold;header.Children.Add(brand);
        DockPanel.SetDock(header,Dock.Top);root.Children.Add(header);
        var footer=new StackPanel{Margin=new Thickness(0,12,0,0)};DockPanel.SetDock(footer,Dock.Bottom);root.Children.Add(footer);
        // Composer: one rounded, softly elevated surface holding the attachment chip, field and actions.
        var stack=new StackPanel();
        attachmentTray.Margin=new Thickness(8,2,8,4);attachmentTray.Visibility=Visibility.Collapsed;stack.Children.Add(attachmentTray);
        var row=new DockPanel();
        var send=IconButton("\uE74A","Send",Submit,true,38);DockPanel.SetDock(send,Dock.Right);row.Children.Add(send);
        var attach=IconButton("\uE710","Attach an image, 3D model or text prompt",()=>{var dlg=new OpenFileDialog{Filter=OpenFilter};if(dlg.ShowDialog()==true)AcceptFile(dlg.FileName);else composer.Focus();},false,38);
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
        // Dropping a supported file anywhere on the window (including the message field) takes it in.
        // Unsupported files show the "not allowed" cursor while dragging.
        AllowDrop=true;
        Func<DragEventArgs,string> dropped=e=>{var files=e.Data.GetData(DataFormats.FileDrop) as string[];return files==null?null:files.FirstOrDefault(f=>Accepted.Contains(Path.GetExtension(f).ToLowerInvariant()));};
        PreviewDragEnter+=(s,e)=>{e.Effects=dropped(e)!=null?DragDropEffects.Copy:DragDropEffects.None;e.Handled=true;};
        PreviewDragOver+=(s,e)=>{e.Effects=dropped(e)!=null?DragDropEffects.Copy:DragDropEffects.None;e.Handled=true;};
        PreviewDrop+=(s,e)=>{string hit=dropped(e);if(hit!=null)AcceptFile(hit);e.Handled=true;};
        details.IsReadOnly=true;details.VerticalScrollBarVisibility=ScrollBarVisibility.Auto;details.Height=90;
        details.Background=wash;details.Foreground=ink;details.BorderThickness=new Thickness(0);details.Padding=new Thickness(8);details.FontFamily=new FontFamily("Cascadia Mono, Consolas");details.FontSize=12;
        // Jobs stack between the conversation and the composer, oldest first; the list scrolls once it grows.
        jobScroller.Content=jobList;jobScroller.MaxHeight=230;jobScroller.Margin=new Thickness(0,0,0,10);
        jobScroller.VerticalScrollBarVisibility=ScrollBarVisibility.Auto;jobScroller.Visibility=Visibility.Collapsed;
        footer.Children.Insert(footer.Children.IndexOf(composerCard),jobScroller);
        footer.Children.Insert(footer.Children.IndexOf(composerCard),actionBar);
        // The raw build log stays out of the way until Ctrl + L.
        buildLog.Header="Build log  (Ctrl + L)";buildLog.Content=details;buildLog.Foreground=muted;buildLog.Margin=new Thickness(4,10,0,0);
        buildLog.Visibility=Visibility.Collapsed;footer.Children.Add(buildLog);
        PreviewKeyDown+=(s,e)=>{
            if(e.Key==Key.L&&(Keyboard.Modifiers&ModifierKeys.Control)!=0){
                bool show=buildLog.Visibility!=Visibility.Visible;
                buildLog.Visibility=show?Visibility.Visible:Visibility.Collapsed;buildLog.IsExpanded=show;e.Handled=true;
            }
        };
        history.VerticalScrollBarVisibility=ScrollBarVisibility.Auto;history.Content=cards;root.Children.Add(history);
        AddText("What would you like to build?",20);
        var heartbeat=new System.Windows.Threading.DispatcherTimer{Interval=TimeSpan.FromSeconds(1)};
        heartbeat.Tick+=(s,e)=>{if(current!=null)UpdateJob(current);};heartbeat.Start();
        Loaded+=(s,e)=>composer.Focus();
        Closing+=(s,e)=>{
            if(!busy)return;
            if(MessageBox.Show(this,"A build is still running. Cancel it and close FORGE?","FORGE",MessageBoxButton.YesNo,MessageBoxImage.Question)!=MessageBoxResult.Yes){e.Cancel=true;return;}
            foreach(var job in pending)job.Cancelled=true;
            if(current!=null){current.Cancelled=true;KillTree(current.Proc);}
        };
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
            var panel=new StackPanel();
            string caption=Caption(path);
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
        var panel=new StackPanel();string caption=Caption(path);
        if(caption!="image"){var label=Label(caption,17);label.FontWeight=FontWeights.SemiBold;label.Margin=new Thickness(4,0,0,8);panel.Children.Add(label);}
        panel.Children.Add(new Image{Source=Preview.Picture(path),Height=300,HorizontalAlignment=HorizontalAlignment.Left});
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
        string source=attachment;
        composer.Clear();if(mode!="chat")SetAttachment(null);
        AddText(raw,17);
        // Rigging an image builds its model first, so the preset applies there too.
        bool rigsImage=mode=="rig"&&source!=null&&new[]{".png",".jpg",".jpeg",".webp"}.Contains(Path.GetExtension(source).ToLowerInvariant());
        if(mode=="model"||mode=="image"||rigsImage){
            string quality=Intent.Quality(raw);
            if(quality=="high")AddNote(mode=="image"?"High quality: painted, then upscaled 4\u00D7 to 3072 px. Takes a little longer.":"High quality: 1024 geometry, 2048 px texture atlas, 4K Unity textures. Takes longer; falls back to standard if your GPU runs short.");
            else if(quality=="draft")AddNote("Draft quality: faster, rougher geometry and 1K textures.");
        }
        // Chat runs beside the job queue so a long GPU build never holds up a conversation.
        if(mode=="chat"){RunChat(raw,source);return;}
        var named=System.Text.RegularExpressions.Regex.Match(raw,@"\b(?:named|called)\s+([A-Za-z0-9_-]{1,48})",System.Text.RegularExpressions.RegexOptions.IgnoreCase);
        string name=named.Success?named.Groups[1].Value:null;
        // Derived outputs take the name of the file they come from.
        if(name==null&&source!=null&&(mode=="rig"||mode=="upscale"||mode=="background"))
            name=Caption(source)+" "+(mode=="rig"?"Rigged":mode=="upscale"?"Upscaled":"Cutout");
        if(name==null&&(mode=="model"||mode=="image")){
            if(askNames){AskName(raw,source);return;}
            name=FallbackNames(raw)[0];
        }
        Enqueue(raw,source,name);
    }
    void AddNote(string text){cards.Children.Add(new TextBlock{Text=text,FontSize=12.5,Foreground=muted,TextWrapping=TextWrapping.Wrap,Margin=new Thickness(4,-4,4,8)});}
    void Enqueue(string raw,string source,string name){
        string mode=Intent.Mode(raw);
        var job=new Job{Raw=raw,Source=source,Mode=mode,Name=String.IsNullOrEmpty(name)?(mode=="image"?"Image":"Model"):CleanName(name).Length>0?CleanName(name):"Project",Quality=Intent.Quality(raw)};
        job.Anchor=cards.Children.Count>0?(FrameworkElement)cards.Children[cards.Children.Count-1]:null;
        JobCard(job);pending.Enqueue(job);
        if(!busy)Drain();
    }
    static string KindLabel(Job job){
        string kind=job.Mode=="image"?"Image":job.Mode=="rig"?"Rigging":job.Mode=="upscale"?"Upscale":job.Mode=="background"?"Background removal":"3D model";
        return kind+(job.Quality=="high"&&(job.Mode=="model"||job.Mode=="image")?" \u00B7 high quality":job.Quality=="draft"&&job.Mode=="model"?" \u00B7 draft":"");
    }
    // Compact card under the composer: name, state pill, live detail, progress and Cancel.
    void JobCard(Job job){
        var title=new TextBlock{Text=job.Name,FontSize=14,FontWeight=FontWeights.SemiBold,Foreground=ink,VerticalAlignment=VerticalAlignment.Center,TextTrimming=TextTrimming.CharacterEllipsis,MaxWidth=320};
        job.Pill=new TextBlock{FontSize=11.5,FontWeight=FontWeights.SemiBold,VerticalAlignment=VerticalAlignment.Center};
        var pill=new Border{CornerRadius=new CornerRadius(8),Padding=new Thickness(8,1,8,2),Margin=new Thickness(8,0,0,0),Child=job.Pill,VerticalAlignment=VerticalAlignment.Center};
        var top=new StackPanel{Orientation=Orientation.Horizontal};top.Children.Add(title);top.Children.Add(pill);
        job.Detail=new TextBlock{FontSize=12.5,Foreground=muted,Margin=new Thickness(0,2,0,0),TextTrimming=TextTrimming.CharacterEllipsis};
        job.Bar=new ProgressBar{Height=3,Margin=new Thickness(0,7,0,0),BorderThickness=new Thickness(0),Background=wash,Foreground=accent,Visibility=Visibility.Collapsed};
        var text=new StackPanel{VerticalAlignment=VerticalAlignment.Center};text.Children.Add(top);text.Children.Add(job.Detail);text.Children.Add(job.Bar);
        job.Action=Button("Cancel",()=>CancelJob(job));job.Action.FontSize=12.5;job.Action.Padding=new Thickness(12,5,12,5);job.Action.VerticalAlignment=VerticalAlignment.Center;
        System.Windows.Automation.AutomationProperties.SetName(job.Action,"Cancel "+job.Name);
        var row=new DockPanel();DockPanel.SetDock(job.Action,Dock.Right);row.Children.Add(job.Action);row.Children.Add(text);
        job.Card=new Border{Child=row,Background=card,BorderBrush=line,BorderThickness=new Thickness(1),CornerRadius=new CornerRadius(14),Padding=new Thickness(14,9,8,9),Margin=new Thickness(0,0,0,6),Cursor=Cursors.Hand,ToolTip=job.Raw};
        job.Card.MouseLeftButtonUp+=(s,e)=>{if(job.Anchor!=null)job.Anchor.BringIntoView();};
        jobList.Children.Add(job.Card);jobScroller.Visibility=Visibility.Visible;jobScroller.ScrollToEnd();
        SetState(job,"Queued");
    }
    void SetState(Job job,string state){
        job.Pill.Text=state=="Done"?"Done \u2713":state;
        var pill=(Border)job.Pill.Parent;
        bool working=state=="Working";
        pill.Background=working?accentSoft:state=="Failed"?Paint("#26E5484D"):wash;
        job.Pill.Foreground=working?accent:state=="Failed"?danger:state=="Done"?accent:muted;
        job.Bar.Visibility=working?Visibility.Visible:Visibility.Collapsed;
        if(state=="Queued")job.Detail.Text=KindLabel(job)+" \u00B7 waiting in line";
        if(state=="Done"||state=="Failed"||state=="Cancelled"){
            job.Done=true;job.Card.Opacity=state=="Done"?1:.75;
            if(state!="Cancelled"||job.Started!=default(DateTime))
                job.Detail.Text=KindLabel(job)+" \u00B7 "+(state=="Done"?"finished":state=="Failed"?"stopped":"cancelled")+(job.Started!=default(DateTime)?" after "+Elapsed(DateTime.Now-job.Started):"");
            else job.Detail.Text=KindLabel(job)+" \u00B7 cancelled";
            // Finished cards trade Cancel for a dismiss button.
            job.Action.Content=new TextBlock{Text="\uE711",FontFamily=new FontFamily(Glyphs),FontSize=10};
            job.Action.ToolTip="Dismiss";job.Action.Padding=new Thickness(10,7,10,7);
            System.Windows.Automation.AutomationProperties.SetName(job.Action,"Dismiss "+job.Name);
        }
    }
    static string Elapsed(TimeSpan t){return t.TotalHours>=1?t.ToString(@"h\:mm\:ss"):t.ToString(@"m\:ss");}
    void UpdateJob(Job job){
        if(job.Done)return;
        job.Detail.Text=KindLabel(job)+" \u00B7 "+job.Stage+" \u00B7 "+Elapsed(DateTime.Now-job.Started);
    }
    void CancelJob(Job job){
        if(job.Done){jobList.Children.Remove(job.Card);if(jobList.Children.Count==0)jobScroller.Visibility=Visibility.Collapsed;return;}
        if(job.Cancelled)return;
        job.Cancelled=true;
        if(job==current&&job.Proc!=null){job.Stage="Cancelling";UpdateJob(job);KillTree(job.Proc);return;}
        SetState(job,"Cancelled");Say(job,"\U0001F6D1 Cancelled before it started.");
    }
    // Stops the runner and everything it launched (FLUX, TRELLIS, Blender, UniRig).
    static void KillTree(Process process){
        try{
            if(process==null||process.HasExited)return;
            using(var kill=Process.Start(new ProcessStartInfo("taskkill.exe","/PID "+process.Id+" /T /F"){UseShellExecute=false,CreateNoWindow=true}))kill.WaitForExit(15000);
        }catch(Exception){}
    }
    // A conversational line in the chat, tagged with the project it belongs to.
    FrameworkElement Say(Job job,string text){
        var line=new TextBlock{FontSize=14.5,Foreground=ink,TextWrapping=TextWrapping.Wrap,Margin=new Thickness(4,8,4,4),MaxWidth=760,HorizontalAlignment=HorizontalAlignment.Left};
        line.Inlines.Add(new System.Windows.Documents.Run(job.Name){FontWeight=FontWeights.SemiBold,Foreground=accent});
        line.Inlines.Add(new System.Windows.Documents.Run("  "+text));
        cards.Children.Add(line);if(job.Anchor==null)job.Anchor=line;
        history.UpdateLayout();history.ScrollToEnd();return line;
    }
    // An image inside the conversation, on a dark plate so cutouts read clearly.
    void ShowPicture(string path,bool cutout){
        try{
            var img=new Image{Source=Preview.Picture(path),Height=220,Stretch=Stretch.Uniform};
            var plate=new Border{Child=img,CornerRadius=new CornerRadius(12),Background=cutout?Paint("#1E252C"):Brushes.Transparent,Padding=new Thickness(cutout?10:0),
                                 Margin=new Thickness(4,4,4,8),HorizontalAlignment=HorizontalAlignment.Left,ClipToBounds=true,ToolTip=path,Cursor=Cursors.Hand};
            plate.MouseLeftButtonUp+=(s,e)=>{try{Process.Start(new ProcessStartInfo(path){UseShellExecute=true});}catch(Exception){}};
            cards.Children.Add(plate);history.UpdateLayout();history.ScrollToEnd();
        }catch(Exception){}
    }
    static readonly Random variety=new Random();
    static string Pick(params string[] options){return options[variety.Next(options.Length)];}
    // Turns runner events into conversation: stages, the prompt, and pictures as they land.
    void Narrate(Job job,string data,string asset){
        if(data.StartsWith("[stage] ")){
            string stage=data.Substring(8);
            job.Stage=stage.Replace(" (high quality)","").Replace(" (draft)","");UpdateJob(job);job.Bar.IsIndeterminate=true;
            bool high=stage.Contains("high quality");
            if(stage.StartsWith("Generating image")&&job.Mode!="image")Say(job,"\U0001F3A8 "+Pick("Painting the reference image","Sketching the reference image","Painting a reference for the sculpt")+(high?" in high quality":"")+"\u2026");
            else if(stage.StartsWith("Building textured model (standard retry)"))Say(job,"\u26A0\uFE0F High quality was too heavy for the GPU this time, so I'm finishing at standard quality.");
            else if(stage.StartsWith("Building textured model"))Say(job,"\U0001F9F1 "+Pick("Now sculpting it in 3D","Time to sculpt it in 3D","Shaping the 3D model")+(high?" at high quality (1024 geometry, 2K textures)":"")+". This is the longest step, so hang tight!");
            else if(stage.StartsWith("Upscaling image (high quality)"))Say(job,"\U0001F50D Painted! Now upscaling it 4\u00D7 for extra detail\u2026");
            else if(stage=="Preparing Unity files")Say(job,"\U0001F4E6 Packing the Unity files and sharpening the textures. Almost there!");
            else if(stage=="Preparing model for rigging")Say(job,"\U0001F9B4 Getting the model ready for rigging\u2026");
            else if(stage=="Rigging with UniRig")Say(job,"\U0001F9B4 UniRig is placing bones and skin weights on the GPU. Next up: your rigged FBX!");
        }
        else if(data.StartsWith("[prompt] ")){
            string prompt=data.Substring(9);if(prompt.Length>260)prompt=prompt.Substring(0,257)+"\u2026";
            Say(job,"\U0001F4DD "+Pick("Here's the prompt I'll use:","I polished your idea into:","Here's how I'll describe it:")+" \u201C"+prompt+"\u201D  Next up: the reference image \U0001F3A8");
        }
        else if(data.StartsWith("[show] image ")){
            Say(job,"\U0001F440 "+Pick("Hey, look, here's the reference image!","Here's the reference image!","Look at this reference!")+" Next up: sculpting it in 3D \U0001F9F1");
            ShowPicture(data.Substring(13),false);
        }
        else if(data.StartsWith("[watch] cutout ")){
            string path=data.Substring(15);
            if(job.Watch!=null)job.Watch.Stop();
            job.Watch=new System.Windows.Threading.DispatcherTimer{Interval=TimeSpan.FromSeconds(1)};
            job.Watch.Tick+=(s,e)=>{
                if(job.Done){job.Watch.Stop();return;}
                try{if(!File.Exists(path)||new FileInfo(path).Length==0||DateTime.Now-File.GetLastWriteTime(path)<TimeSpan.FromSeconds(1))return;}catch(IOException){return;}
                job.Watch.Stop();
                Say(job,"\u2702\uFE0F "+Pick("Background removed! This cutout is what I'm sculpting from.","Cut it out of the background. Sculpting from this now.","Here's the clean cutout I'm sculpting from."));
                ShowPicture(path,true);
            };
            job.Watch.Start();
        }
        else if(data.StartsWith("[show] model ")){
            Say(job,"\u2728 "+Pick("The 3D model is ready, give it a spin!","Here it is in 3D, drag to spin it!","Sculpted! Drag to spin it.")+" Next up: Unity files \U0001F4E6");
            AddModel(data.Substring(13));job.ModelShown=true;
        }
        else if(data.Contains("[flow]")){
            var step=System.Text.RegularExpressions.Regex.Match(data,@"\]\s+(\d+)/(\d+).*?~([\d.]+)s left");
            if(step.Success){int done=int.Parse(step.Groups[1].Value),count=int.Parse(step.Groups[2].Value);
                job.Bar.IsIndeterminate=false;job.Bar.Value=100.0*done/Math.Max(1,count);
                job.Stage="Sculpting \u00B7 step "+done+" of "+count;UpdateJob(job);}
        }
    }
    async void RunChat(string raw,string source){
        var thinking=new TextBlock{Text="\U0001F4AD Thinking\u2026",FontSize=13,Foreground=muted,Margin=new Thickness(4,4,4,8)};
        cards.Children.Add(thinking);history.ScrollToEnd();
        await chatGate.WaitAsync();
        string scratch=Path.Combine(Path.GetTempPath(),"FORGE-chat-"+Guid.NewGuid().ToString("N"));
        try{Directory.CreateDirectory(scratch);await Chat(raw,source,scratch);}
        catch(Exception ex){AddText("\U0001F615 Chat stopped: "+ex.GetBaseException().Message,14);}
        finally{cards.Children.Remove(thinking);chatGate.Release();try{Directory.Delete(scratch,true);}catch(Exception){}}
    }
    // A project name is chosen before generation starts, so every job folder is recognizable.
    void AskName(string raw,string source){
        var panel=new StackPanel();
        var title=Label("Name this project",15);title.FontWeight=FontWeights.SemiBold;panel.Children.Add(title);
        panel.Children.Add(new TextBlock{Text="Pick a suggestion or type your own. Your files are saved under this name.",FontSize=12.5,Foreground=muted,TextWrapping=TextWrapping.Wrap,Margin=new Thickness(0,2,0,0)});
        var chips=new WrapPanel{Margin=new Thickness(-3,10,0,8)};
        panel.Children.Add(chips);
        var box=new TextBox{FontSize=14,Padding=new Thickness(8,6,8,6),Background=Brushes.Transparent,Foreground=ink,CaretBrush=ink,BorderThickness=new Thickness(0),VerticalContentAlignment=VerticalAlignment.Center,FocusVisualStyle=null,MaxLength=40};
        System.Windows.Automation.AutomationProperties.SetName(box,"Project name");
        var hint=new TextBlock{Text="Or type a name",FontSize=14,Foreground=muted,Margin=new Thickness(11,0,0,0),VerticalAlignment=VerticalAlignment.Center,IsHitTestVisible=false};
        box.TextChanged+=(s,e)=>hint.Visibility=box.Text.Length==0?Visibility.Visible:Visibility.Collapsed;
        var field=new Grid();field.Children.Add(box);field.Children.Add(hint);
        var frame=new Border{CornerRadius=new CornerRadius(10),BorderBrush=line,BorderThickness=new Thickness(1),Background=paper,Child=field,Margin=new Thickness(0,0,6,0)};
        box.GotKeyboardFocus+=(s,e)=>frame.BorderBrush=accent;box.LostKeyboardFocus+=(s,e)=>frame.BorderBrush=line;
        var row=new DockPanel();
        bool done=false;
        Action<string> choose=null;
        var start=Button("Start",()=>choose(box.Text),true);start.Margin=new Thickness(0);
        DockPanel.SetDock(start,Dock.Right);row.Children.Add(start);row.Children.Add(frame);panel.Children.Add(row);
        var cardBorder=new Border{Child=panel,Background=card,Padding=new Thickness(16),CornerRadius=new CornerRadius(16),BorderBrush=line,BorderThickness=new Thickness(1),Margin=new Thickness(0,4,8,8),MaxWidth=640,HorizontalAlignment=HorizontalAlignment.Left};
        choose=value=>{
            string name=CleanName(value);
            if(done)return;
            if(name.Length==0){box.Focus();return;}
            done=true;
            // The question has served its purpose; the project now lives in its job card.
            cards.Children.Remove(cardBorder);
            Enqueue(raw,source,name);composer.Focus();
        };
        box.KeyDown+=(s,e)=>{if(e.Key==Key.Enter){choose(box.Text);e.Handled=true;}};
        cards.Children.Add(cardBorder);history.UpdateLayout();history.ScrollToEnd();box.Focus();
        // Prompt-based names appear at once; Qwen's ideas are added when the CPU model finishes.
        var offered=new List<string>();
        Action<string> offer=suggestion=>{
            if(offered.Any(x=>String.Equals(x,suggestion,StringComparison.OrdinalIgnoreCase)))return;
            offered.Add(suggestion);string n=suggestion;chips.Children.Add(Button(n,()=>choose(n),false,16));
        };
        if(source!=null&&CleanName(Caption(source)).Length>0)offer(CleanName(Caption(source)));
        foreach(string n in FallbackNames(raw).Take(3))offer(n);
        if(config==null||!config.ContainsKey("chat"))return;
        var thinking=new TextBlock{Text="Thinking of more names\u2026",FontSize=12.5,Foreground=muted,Margin=new Thickness(8,0,0,0),VerticalAlignment=VerticalAlignment.Center};
        chips.Children.Add(thinking);
        SuggestNames(raw).ContinueWith(t=>{
            chips.Children.Remove(thinking);
            if(done||t.IsFaulted)return;
            foreach(string n in t.Result.Take(3))offer(n);
        },TaskScheduler.FromCurrentSynchronizationContext());
    }
    static string CleanName(string value){
        string name=System.Text.RegularExpressions.Regex.Replace(value??"",@"[^A-Za-z0-9 _-]"," ");
        name=System.Text.RegularExpressions.Regex.Replace(name.Replace('_',' '),@"\s+"," ").Trim();
        return name.Length>40?name.Substring(0,40).Trim():name;
    }
    static string Caption(string path){
        string stem=System.Text.RegularExpressions.Regex.Replace(Path.GetFileNameWithoutExtension(path),@"_\d{8}_\d{6}_\d+$","");
        return stem.Replace('_',' ');
    }
    // Names drawn from the prompt itself: used when Qwen is unavailable or short of ideas.
    static List<string> FallbackNames(string raw){
        var stop=new HashSet<string>(StringComparer.OrdinalIgnoreCase){"forge","build","make","mold","generate","create","imagine","image","please","can","could","would","you","me","my","a","an","the","of","with","and","for","in","on","at","to","some","that","this","it","is","very","named","called","model","3d",
            "super","superior","supreme","quality","high","hq","prime","premium","ultra","best","detailed","res","hi","hires","lowres","masterpiece","draft","low"};
        var words=System.Text.RegularExpressions.Regex.Matches(raw,@"[A-Za-z][A-Za-z0-9]*").Cast<System.Text.RegularExpressions.Match>()
            .Select(m=>m.Value).Where(w=>w.Length>1&&!stop.Contains(w)).Select(w=>Char.ToUpperInvariant(w[0])+w.Substring(1)).ToList();
        var list=new List<string>();
        Action<IEnumerable<string>> add=ws=>{string n=String.Join(" ",ws);if(n.Length>0&&n.Length<=40&&!list.Any(x=>String.Equals(x,n,StringComparison.OrdinalIgnoreCase)))list.Add(n);};
        if(words.Count>0){
            add(words.Skip(Math.Max(0,words.Count-2)));add(words.Skip(Math.Max(0,words.Count-3)));
            add(new[]{words[words.Count-1]});add(words.Take(2));
            add(new[]{words[words.Count-1],"Prop"});add(new[]{words[words.Count-1],"Asset"});
        }
        for(int i=1;list.Count<3;i++)add(new[]{"Project",i.ToString()});
        return list;
    }
    async Task<List<string>> SuggestNames(string raw){
        var result=new List<string>();
        if(config!=null&&config.ContainsKey("chat")){
            string scratch=Path.Combine(Path.GetTempPath(),"FORGE-names-"+Guid.NewGuid().ToString("N"));
            try{
                Directory.CreateDirectory(scratch);
                string request=Path.Combine(scratch,"prompt.txt"),reply=Path.Combine(scratch,"names.txt");
                File.WriteAllText(request,raw);
                var info=new ProcessStartInfo(config["python"],Quote(Path.Combine(AppDir,"names.py"))+" "+Quote(request)+" "+Quote(configPath)+" "+Quote(reply)){UseShellExecute=false,CreateNoWindow=true};
                using(var process=Process.Start(info)){
                    bool exited=await Task.Run(()=>process.WaitForExit(120000));
                    if(!exited){try{process.Kill();}catch(InvalidOperationException){}}
                    else if(process.ExitCode==0&&File.Exists(reply))
                        foreach(string line in File.ReadAllLines(reply)){string n=CleanName(line);if(n.Length>0&&!result.Any(x=>String.Equals(x,n,StringComparison.OrdinalIgnoreCase)))result.Add(n);}
                }
            }catch(Exception){}
            finally{try{Directory.Delete(scratch,true);}catch(Exception){}}
        }
        return result;
    }
    async void Drain(){busy=true;
        while(pending.Count>0){
            var job=pending.Dequeue();
            if(job.Cancelled)continue;
            current=job;job.Started=DateTime.Now;job.Stage="Starting";SetState(job,"Working");UpdateJob(job);job.Bar.IsIndeterminate=true;
            string job_dir=null;
            try{
                string mode=job.Mode,source=job.Source;
                bool image=mode=="image"||mode=="upscale"||mode=="background";
                if(mode=="model"&&source==null)Say(job,"\U0001F680 "+Pick("Let's make it!","Here we go!","On it!")+" First I'll polish your prompt, then paint a reference image.");
                else if(mode=="model")Say(job,"\U0001F680 Building a 3D model from your image. First I'll cut out the background.");
                else if(mode=="image")Say(job,"\U0001F3A8 "+Pick("Painting it now, one moment!","Grabbing my brushes, one moment!")+(job.Quality=="high"?" Then I\u2019ll upscale it 4\u00D7 for extra detail.":""));
                else if(mode=="background")Say(job,"\u2702\uFE0F Cutting it out of the background\u2026");
                else if(mode=="upscale")Say(job,"\U0001F50D Upscaling it 4\u00D7\u2026");
                else if(mode=="rig")Say(job,"\U0001F9B4 Let's give it a skeleton!"+(source!=null&&!new[]{".glb",".fbx"}.Contains(Path.GetExtension(source).ToLowerInvariant())?" I'll build the 3D model first.":""));
                string folder=CleanName(job.Name).Replace(' ','_');
                string id=(folder.Length>0?folder:image?"image":"forge")+"_"+DateTime.Now.ToString("yyyyMMdd_HHmmss_fffffff");
                job_dir=Path.Combine(config["output"],id);job.Folder=job_dir;Directory.CreateDirectory(job_dir);File.WriteAllText(Path.Combine(job_dir,"prompt.txt"),job.Raw);
                string log=Path.Combine(job_dir,"pipeline.log");details.Clear();
                string inputArgument="";
                if(source!=null){string copy=Path.Combine(job_dir,"input"+Path.GetExtension(source));File.Copy(source,copy);inputArgument=" --input "+Quote(copy);}
                string asset=Path.Combine(job_dir,id+(image?".png":mode=="rig"?".fbx":".glb"));
                var info=new ProcessStartInfo(config["python"],"-u "+Quote(Path.Combine(AppDir,"runner.py"))+" --config "+Quote(configPath)+" --job "+Quote(job_dir)+" --mode "+mode+inputArgument){
                    UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true,WorkingDirectory=job_dir};
                using(var writer=File.CreateText(log))using(var proc=new Process{StartInfo=info}){
                    writer.AutoFlush=true;
                    DataReceivedEventHandler line=(s,e)=>{if(e.Data==null)return;lock(writer)writer.WriteLine(e.Data);
                        Dispatcher.BeginInvoke(new Action(()=>{
                            if(!job.Cancelled)Narrate(job,e.Data,asset);
                            if(details.Text.Length>40000)details.Text=details.Text.Substring(20000);details.AppendText(e.Data+Environment.NewLine);details.ScrollToEnd();}));};
                    proc.OutputDataReceived+=line;proc.ErrorDataReceived+=line;proc.Start();job.Proc=proc;proc.BeginOutputReadLine();proc.BeginErrorReadLine();
                    if(job.Cancelled)KillTree(proc);
                    await Task.Run(()=>proc.WaitForExit());
                    job.Proc=null;
                    if(job.Cancelled)throw new OperationCanceledException();
                    if(proc.ExitCode!=0)throw new Exception("The build stopped.");
                }
                if(job.Watch!=null)job.Watch.Stop();
                if(mode=="rig"){Say(job,"\U0001F389 "+Pick("It's rigged!","Bones in place, it's rigged!")+" Save the FBX and drop it into Unity.");cards.Children.Add(Button("Save rigged FBX",()=>SaveAsset(asset)));}
                else if(image){Say(job,"\U0001F389 "+Pick("Here it is!","All done, here it is!","Ta-da!"));AddImage(asset);}
                else{Say(job,"\U0001F389 "+Pick("All done!","Finished!","It's ready!")+" Rig it, save it, or expand it for a closer look.");if(!job.ModelShown){AddModel(asset);job.ModelShown=true;}}
                string done_dir=job_dir;
                var open=Button("\U0001F4C1 Open folder",()=>{try{Process.Start("explorer.exe",Quote(done_dir));}catch(Exception){}});
                open.HorizontalAlignment=HorizontalAlignment.Left;open.Margin=new Thickness(4,0,4,8);open.ToolTip=done_dir;cards.Children.Add(open);
                history.ScrollToEnd();SetState(job,"Done");
            }catch(OperationCanceledException){
                if(job.Watch!=null)job.Watch.Stop();
                SetState(job,"Cancelled");Say(job,"\U0001F6D1 Cancelled. I cleaned up its unfinished files.");
                // Partial output from a cancelled job is only clutter; delete it when the processes let go.
                if(job_dir!=null){string partial=job_dir;Task.Run(()=>{for(int i=0;i<10;i++){try{Directory.Delete(partial,true);return;}catch(Exception){System.Threading.Thread.Sleep(1000);}}});}
            }catch(Exception ex){
                if(job.Watch!=null)job.Watch.Stop();
                failed++;SetState(job,"Failed");
                Say(job,"\U0001F615 "+ex.GetBaseException().Message+" Press Ctrl + L to see the build log.");
            }
            current=null;
        }
        busy=false;history.ScrollToEnd();
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
                    // The core runtime still works when only the chat/UniRig step failed.
                    if(!File.Exists(cfg))throw;
                    MessageBox.Show(ex.GetBaseException().Message+"\n\nImage and 3D generation are available. Chat and rigging finish installing the next time FORGE opens.","FORGE");
                }
            }
            var app=new Application();var window=new Forge(cfg);
            if(args.Length>=2 && args[0]=="--preview")window.ContentRendered+=(s,e)=>{
                window.AddModel(args[1]);
                if(args.Length>=3){window.UpdateLayout();var size=((FrameworkElement)window.Content).RenderSize;var shot=new RenderTargetBitmap((int)size.Width,(int)size.Height,96,96,PixelFormats.Pbgra32);
                    shot.Render((Visual)window.Content);var enc=new PngBitmapEncoder();enc.Frames.Add(BitmapFrame.Create(shot));using(var stream=File.Create(args[2]))enc.Save(stream);window.Close();}};
            if(args.Length>=2 && args[0]=="--build")window.ContentRendered+=(s,e)=>{window.askNames=false;window.composer.Text=String.Join(" ",args.Skip(1));window.Submit();};
            app.Run(window);return 0;
        }catch(Exception ex){Console.Error.WriteLine(ex.GetBaseException().Message);if(!args.Contains("--quiet"))MessageBox.Show(ex.GetBaseException().Message,"FORGE");return 1;}
    }
}
