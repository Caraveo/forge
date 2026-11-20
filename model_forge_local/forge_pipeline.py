import argparse, shutil, subprocess, sys
from pathlib import Path

INFER=Path(r'C:\Projects\Img\infer.cmd')
TRELLIS=Path(r'C:\Users\Administrator\AppData\Local\trellis-studio\runtime\trellis-cli.exe')
MODELS=Path(r'C:\Users\Administrator\AppData\Local\trellis-studio\models')
TRANSIT=Path(r'C:\Users\Administrator\bin\transit.cmd')

def run(cmd,cwd=None):
    print('[forge] $ '+' '.join(map(str,cmd)),flush=True)
    p=subprocess.Popen(cmd,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
    for line in p.stdout: print(line.rstrip(),flush=True)
    code=p.wait()
    if code: raise RuntimeError(f'command failed with exit code {code}')

def white_cutout(src,dst):
    from PIL import Image
    im=Image.open(src).convert('RGBA'); px=im.load()
    for y in range(im.height):
        for x in range(im.width):
            r,g,b,a=px[x,y]
            if r>=245 and g>=245 and b>=245: px[x,y]=(r,g,b,0)
    dst.parent.mkdir(parents=True,exist_ok=True); im.save(dst,'PNG')

def main():
    ap=argparse.ArgumentParser(prog='forge'); ap.add_argument('inputs',nargs='+'); ap.add_argument('--name',required=True); ap.add_argument('--out',required=True); ap.add_argument('--resolution',type=int,default=512); ap.add_argument('--steps',type=int,default=12); ap.add_argument('--model',default='trellis'); a=ap.parse_args()
    out=Path(a.out).resolve(); job=out.parent; job.mkdir(parents=True,exist_ok=True); image=job/(out.stem+'.png'); cutout=job/(out.stem+'-nb.png')
    paths=[Path(x).expanduser() for x in a.inputs]; refs=[x for x in paths if x.is_file()]
    if refs: shutil.copy2(refs[0],image)
    else: run(['cmd.exe','/d','/c',str(INFER),' '.join(a.inputs),'--out',str(image),'--seed','42'])
    try:
        run(['cmd.exe','/d','/c',str(Path(r'C:\Projects\Background\background.cmd')),str(image),'--out',str(cutout)])
    except Exception as exc:
        print(f'[forge] background AI unavailable: {exc}; using local white-background fallback',flush=True); white_cutout(image,cutout)
    run([str(TRELLIS),'--models',str(MODELS),'--image',str(cutout),'--output',str(out),'--res',str(a.resolution),'--seed','42','--steps',str(a.steps),'--backend','Vulkan','--model',a.model])
    if TRANSIT.exists(): run(['cmd.exe','/d','/c',str(TRANSIT),str(out)],cwd=str(job))
    print(f'[forge] complete: {out}',flush=True)

if __name__=='__main__':
    try: main()
    except Exception as exc: print('[forge] ERROR: '+str(exc),file=sys.stderr); raise
