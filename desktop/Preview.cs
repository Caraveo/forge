using System;
using System.Collections.Generic;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Media.Media3D;
using System.Web.Script.Serialization;

// FORGE writes one indexed triangle mesh in glTF coordinates with embedded base color.
internal sealed class Preview : Grid {
    readonly PerspectiveCamera camera = new PerspectiveCamera();
    Point3D center;
    Rect3D box;
    double radius, yaw = .48, pitch = .16, zoom = 1;
    Point previous;
    static dynamic At(dynamic root, string key, int i) { return root[key][i]; }
    static int Offset(dynamic dict, string key) { return dict.ContainsKey(key) ? (int)dict[key] : 0; }
    static BitmapImage Bitmap(Stream stream) {
        var img = new BitmapImage();
        img.BeginInit(); img.CacheOption = BitmapCacheOption.OnLoad; img.DecodePixelWidth = 1024;
        img.StreamSource = stream; img.EndInit(); img.Freeze(); return img;
    }
    public static BitmapImage Picture(string file) {
        using (var stream = File.OpenRead(file)) return Bitmap(stream);
    }
    public Preview(string file) {
        Height = 335; ClipToBounds = true; Cursor = Cursors.Hand;
        Background = new LinearGradientBrush(Color.FromRgb(49,59,72), Color.FromRgb(21,27,36), 90);
        byte[] data; dynamic doc;
        using (var reader = new BinaryReader(File.OpenRead(file))) {
            if (reader.ReadUInt32() != 0x46546c67 || reader.ReadUInt32() != 2) throw new InvalidDataException("Expected a GLB 2 model.");
            reader.ReadUInt32(); int n = reader.ReadInt32(); reader.ReadUInt32();
            doc = new JavaScriptSerializer().DeserializeObject(System.Text.Encoding.UTF8.GetString(reader.ReadBytes(n)));
            n = reader.ReadInt32(); reader.ReadUInt32(); data = reader.ReadBytes(n);
        }
        dynamic prim = doc["meshes"][0]["primitives"][0], attr = prim["attributes"];
        var mesh = new MeshGeometry3D();
        foreach (string field in new[]{"POSITION","NORMAL","TEXCOORD_0","indices"}) {
            if (field != "indices" && !attr.ContainsKey(field)) continue;
            dynamic accessor = At(doc,"accessors", field=="indices" ? (int)prim[field] : (int)attr[field]);
            dynamic view = At(doc,"bufferViews",(int)accessor["bufferView"]);
            int type = accessor["componentType"], count = accessor["count"];
            int stride = Offset(view,"byteStride");
            if (stride==0) stride = field=="indices" ? (type==5125 ? 4 : type==5123 ? 2 : 1) : field=="TEXCOORD_0" ? 8 : 12;
            int pos = Offset(accessor,"byteOffset")+Offset(view,"byteOffset");
            for(int i=0;i<count;i++,pos+=stride) {
                if(field=="indices") { mesh.TriangleIndices.Add(type==5125 ? BitConverter.ToInt32(data,pos) : type==5123 ? BitConverter.ToUInt16(data,pos) : data[pos]); continue; }
                double x=BitConverter.ToSingle(data,pos), y=BitConverter.ToSingle(data,pos+4);
                if(field=="TEXCOORD_0") mesh.TextureCoordinates.Add(new Point(x,y));
                else if(field=="NORMAL") mesh.Normals.Add(new Vector3D(x,y,BitConverter.ToSingle(data,pos+8)));
                else mesh.Positions.Add(new Point3D(x,y,BitConverter.ToSingle(data,pos+8)));
            }
        }
        mesh.Freeze();
        Brush surface = Brushes.LightSteelBlue;
        if(doc.ContainsKey("textures") && attr.ContainsKey("TEXCOORD_0")) {
            dynamic tex = doc["textures"][0];
            dynamic img = doc["images"][tex.ContainsKey("source") ? (int)tex["source"] : (int)tex["extensions"]["EXT_texture_webp"]["source"]];
            dynamic buf = doc["bufferViews"][(int)img["bufferView"]];
            try { using(var stream=new MemoryStream(data,Offset(buf,"byteOffset"),(int)buf["byteLength"])) surface=new ImageBrush(Bitmap(stream)); }
            catch(NotSupportedException) {
                string png=Path.Combine(Path.GetDirectoryName(file),Path.GetFileNameWithoutExtension(file)+"-asset","Image_0.png");
                if(File.Exists(png)) surface=new ImageBrush(Picture(png));
            }
        }
        var bounds=box=mesh.Bounds;
        center=new Point3D(bounds.X+bounds.SizeX/2,bounds.Y+bounds.SizeY/2,bounds.Z+bounds.SizeZ/2);
        radius=Math.Max(.001,Math.Sqrt(bounds.SizeX*bounds.SizeX+bounds.SizeY*bounds.SizeY+bounds.SizeZ*bounds.SizeZ)/2);
        var material=new DiffuseMaterial(surface);
        var scene=new Model3DGroup();
        scene.Children.Add(new AmbientLight(Color.FromRgb(155,155,155)));
        scene.Children.Add(new DirectionalLight(Colors.White,new Vector3D(-1,-2,-3)));
        scene.Children.Add(new GeometryModel3D(mesh,material){BackMaterial=material});
        scene.Freeze();
        var viewport=new Viewport3D {Camera=camera};
        viewport.Children.Add(new ModelVisual3D {Content=scene}); Children.Add(viewport);
        MouseLeftButtonDown+=(s,e)=>{previous=e.GetPosition(this);CaptureMouse();e.Handled=true;};
        MouseMove+=(s,e)=>{if(!IsMouseCaptured)return; var p=e.GetPosition(this); yaw-=(p.X-previous.X)*.012;
            pitch=Math.Max(-1.5,Math.Min(1.5,pitch+(p.Y-previous.Y)*.012));previous=p;Frame();};
        MouseLeftButtonUp+=(s,e)=>ReleaseMouseCapture();
        PreviewMouseWheel+=(s,e)=>{if(Keyboard.Modifiers.HasFlag(ModifierKeys.Control)){Zoom(e.Delta>0?.84:1.19);e.Handled=true;}};
        SizeChanged+=(s,e)=>Frame(); Frame();
    }
    public void Zoom(double factor){zoom=Math.Max(.32,Math.Min(5,zoom*factor));Frame();}
    public void Reset(){yaw=.48;pitch=.16;zoom=1;Frame();}
    void Frame(){
        double aspect=Math.Max(.25,ActualWidth/Height), tan=Math.Tan(Math.PI*24/180);
        var forward=new Vector3D(Math.Sin(yaw)*Math.Cos(pitch),Math.Sin(pitch),Math.Cos(yaw)*Math.Cos(pitch));
        var right=new Vector3D(Math.Cos(yaw),0,-Math.Sin(yaw));
        var up=Vector3D.CrossProduct(forward,right);
        double distance=radius;
        for(int corner=0;corner<8;corner++){
            var v=new Vector3D(box.SizeX*((corner&1)-.5),box.SizeY*(((corner>>1)&1)-.5),box.SizeZ*(((corner>>2)&1)-.5));
            double extent=Math.Max(Math.Abs(Vector3D.DotProduct(v,right)),Math.Abs(Vector3D.DotProduct(v,up))*aspect);
            distance=Math.Max(distance,Vector3D.DotProduct(v,forward)+1.12*extent/tan);
        }
        var offset=forward*(distance*zoom);
        camera.Position=center+offset;camera.LookDirection=-offset;camera.UpDirection=new Vector3D(0,1,0);
        camera.FieldOfView=48;camera.NearPlaneDistance=radius*.005;camera.FarPlaneDistance=radius*100;
    }
}
