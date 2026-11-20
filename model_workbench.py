import os, queue, subprocess, threading, time, json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

ROOT = Path.cwd()

class Workbench(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Model Forge — 3D AI Workbench')
        self.geometry('1180x760'); self.minsize(980, 640)
        self.configure(bg='#101216')
        self.jobs = queue.Queue(); self.running = False; self.job_no = 0
        self._style(); self._ui(); self._log('Ready. Local command runner connected.')

    def _style(self):
        s=ttk.Style(self); s.theme_use('clam')
        s.configure('TFrame', background='#101216'); s.configure('Panel.TFrame', background='#171a20')
        s.configure('TLabel', background='#171a20', foreground='#d9dee8', font=('Segoe UI',10))
        s.configure('Muted.TLabel', foreground='#8d96a8', font=('Segoe UI',9))
        s.configure('Title.TLabel', background='#101216', foreground='#f3f6fb', font=('Segoe UI Semibold',22))
        s.configure('H.TLabel', foreground='#f3f6fb', font=('Segoe UI Semibold',11))
        s.configure('Accent.TButton', background='#8c7cff', foreground='white', padding=(16,10), font=('Segoe UI Semibold',10))
        s.map('Accent.TButton', background=[('active','#a195ff')])
        s.configure('TButton', background='#242934', foreground='#e6eaf2', padding=(10,7), borderwidth=0)
        s.configure('TEntry', fieldbackground='#20242c', foreground='#f3f6fb', insertcolor='white')
        s.configure('TCombobox', fieldbackground='#20242c', foreground='#f3f6fb')

    def _ui(self):
        top=ttk.Frame(self); top.pack(fill='x', padx=24, pady=(20,12))
        ttk.Label(top,text='MODEL FORGE',style='Title.TLabel').pack(side='left')
        ttk.Label(top,text='  AI 3D model workbench',style='Muted.TLabel').pack(side='left', pady=9)
        ttk.Label(top,text='LOCAL RUNNER  ●',foreground='#65d6a4',background='#101216',font=('Segoe UI',9)).pack(side='right',pady=9)
        body=ttk.Frame(self); body.pack(fill='both',expand=True,padx=24,pady=(0,22)); body.columnconfigure(0,weight=1); body.columnconfigure(1,weight=2); body.rowconfigure(0,weight=1)
        left=ttk.Frame(body,style='Panel.TFrame',padding=18); left.grid(row=0,column=0,sticky='nsew',padx=(0,10)); right=ttk.Frame(body,style='Panel.TFrame',padding=18); right.grid(row=0,column=1,sticky='nsew',padx=(10,0)); right.rowconfigure(2,weight=1); right.columnconfigure(0,weight=1)
        ttk.Label(left,text='Describe a 3D model',style='H.TLabel').pack(anchor='w'); ttk.Label(left,text='The enhancer stays focused on geometry, materials, pose, scale, and Unity readiness.',style='Muted.TLabel',wraplength=360).pack(anchor='w',pady=(5,12))
        self.prompt=tk.Text(left,height=8,bg='#20242c',fg='#f3f6fb',insertbackground='white',relief='flat',wrap='word',font=('Segoe UI',11),padx=12,pady=12); self.prompt.pack(fill='x'); self.prompt.insert('1.0','a small forest cat, stylized low-poly, standing')
        row=ttk.Frame(left); row.pack(fill='x',pady=12); ttk.Button(row,text='Enhance prompt',command=self.enhance).pack(side='left'); ttk.Label(row,text='small model • geometry-first',style='Muted.TLabel').pack(side='left',padx=10)
        ttk.Label(left,text='Quick tips',style='H.TLabel').pack(anchor='w',pady=(10,7)); tips=ttk.Frame(left,style='Panel.TFrame'); tips.pack(fill='x')
        for t in ['low-poly silhouette','neutral T-pose','separate accessories','Unity-ready materials','warm painted colors']:
            ttk.Button(tips,text=t,command=lambda x=t:self.add_tip(x)).pack(fill='x',pady=2)
        opts=ttk.Frame(left,style='Panel.TFrame'); opts.pack(fill='x',pady=(16,0)); ttk.Label(opts,text='Resolution').grid(row=0,column=0,sticky='w'); self.res=tk.StringVar(value='512'); ttk.Combobox(opts,textvariable=self.res,values=['512','1024','1536'],state='readonly',width=8).grid(row=0,column=1,padx=8); ttk.Label(opts,text='Model').grid(row=0,column=2,padx=(15,0)); self.model=tk.StringVar(value='trellis'); ttk.Combobox(opts,textvariable=self.model,values=['trellis','pixal3d'],state='readonly',width=10).grid(row=0,column=3,padx=8)
        ttk.Button(left,text='＋ Add reference image',command=self.ref).pack(anchor='w',pady=(18,0)); self.refpath=ttk.Label(left,text='No reference selected',style='Muted.TLabel'); self.refpath.pack(anchor='w',pady=5)
        ttk.Button(left,text='BUILD  3D MODEL',style='Accent.TButton',command=self.build).pack(fill='x',pady=(18,0))
        ttk.Label(right,text='Workspace',style='H.TLabel').grid(row=0,column=0,sticky='w'); self.status=ttk.Label(right,text='Queue is empty',style='Muted.TLabel'); self.status.grid(row=0,column=0,sticky='e')
        self.queuebox=tk.Listbox(right,height=6,bg='#20242c',fg='#dce2ed',selectbackground='#383256',relief='flat',font=('Consolas',10)); self.queuebox.grid(row=1,column=0,sticky='ew',pady=(10,18))
        tabs=ttk.Notebook(right); tabs.grid(row=2,column=0,sticky='nsew'); right.rowconfigure(2,weight=1)
        self.preview=tk.Text(tabs,bg='#13161b',fg='#b9c2d2',relief='flat',font=('Consolas',10),wrap='word',padx=14,pady=14); tabs.add(self.preview,text='Result / Preview'); self.preview.insert('1.0','Your image and 3D model will appear here.\n\nThe runner will preserve the output folder and show the exact paths in the log.')
        self.log=tk.Text(tabs,bg='#13161b',fg='#92e6bc',relief='flat',font=('Consolas',9),wrap='word',padx=14,pady=14); tabs.add(self.log,text='Logs & Debug');

    def _log(self,msg): self.log.insert('end',f'[{time.strftime("%H:%M:%S")}] {msg}\n'); self.log.see('end')
    def add_tip(self,t): self.prompt.insert('end', ', '+t); self._log('Tip applied: '+t)
    def enhance(self):
        p=self.prompt.get('1.0','end').strip(); extra='; 3D asset, clear readable silhouette, centered full body, consistent proportions, clean topology, PBR-friendly materials, isolated neutral background, ready for Unity'
        if '3D asset' not in p: self.prompt.delete('1.0','end'); self.prompt.insert('1.0',p+extra)
        self._log('Prompt enhanced with 3D geometry + Unity constraints.')
    def ref(self):
        f=filedialog.askopenfilename(filetypes=[('Images','*.png *.jpg *.jpeg *.webp')]);
        if f: self.refpath.config(text=f); self._log('Reference: '+f)
    def build(self):
        p=self.prompt.get('1.0','end').strip()
        if not p: return messagebox.showwarning('Prompt needed','Describe the model first.')
        self.job_no+=1; name='forge_%03d'%self.job_no; out=ROOT/name; out.mkdir(exist_ok=True)
        self.jobs.put((name,p,out)); self.queuebox.insert('end',f'QUEUED   {name}   dimension → image → GLB'); self.status.config(text='Job queued'); self._log(f'Queued {name}: {p}')
        if not self.running: threading.Thread(target=self.worker,daemon=True).start()
    def worker(self):
        self.running=True
        while not self.jobs.empty():
            name,p,out=self.jobs.get(); self.after(0,lambda n=name:self.status.config(text='Running '+n)); self.after(0,lambda:self._log('Starting dimension pipeline…'))
            cmd=['dimension','--name',name,'--resolution',self.res.get(),'--model',self.model.get(),'--out',str(out),p]
            try:
                self.after(0,lambda:self._log('COMMAND: '+' '.join(cmd)))
                proc=subprocess.Popen(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
                for line in proc.stdout: self.after(0,lambda x=line.rstrip():self._log(x))
                code=proc.wait()
                if code: raise RuntimeError('dimension exited with code '+str(code))
                files=list(out.rglob('*')); self.after(0,lambda f=files,n=name:self.done(n,f))
            except Exception as e: self.after(0,lambda n=name,e=e:self.fail(n,e))
        self.running=False; self.after(0,lambda:self.status.config(text='Queue is empty'))
    def done(self,n,files):
        self.queuebox.insert('end',f'DONE     {n}   ✓ image + model'); self.preview.delete('1.0','end'); self.preview.insert('1.0',f'JOB COMPLETE: {n}\n\nSuggested next step\nOpen the GLB/FBX in Unity or run transit for Unity extraction.\n\nOUTPUTS\n'+'\n'.join(str(x) for x in files)); self._log('Completed successfully. Outputs are listed in Result / Preview.')
    def fail(self,n,e): self.queuebox.insert('end',f'ERROR    {n}   ✕ see logs'); self._log('ERROR: '+str(e)); self._log('Correction: verify dimension is on PATH and retry with a smaller resolution.')

if __name__=='__main__': Workbench().mainloop()
