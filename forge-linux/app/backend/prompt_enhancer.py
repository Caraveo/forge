"""Local 3D prompt compiler. Uses the installed ROCm PyTorch runtime for scoring.
It is intentionally domain-specific: this is a prompt compiler for text->image->3D,
not a general chatbot and it never sends text off-machine.
"""
import argparse, json, re, sys
from pathlib import Path
import torch

DOMAINS = {
    'geometry': ['clear silhouette','full body','readable proportions','clean topology'],
    'pose': ['neutral standing pose','balanced center of gravity','symmetrical presentation'],
    'surface': ['hand-painted PBR materials','coherent color blocking','subtle roughness variation'],
    'generation': ['centered studio view','isolated neutral background','soft three-point lighting'],
    'unity': ['game-ready scale','separate accessories','Unity-ready asset preparation'],
}

def compile_prompt(raw: str) -> dict:
    text = re.sub(r'\s+', ' ', raw.strip()).strip(' ,.')
    # A tiny torch scorer keeps enhancement deterministic and exercises the local GPU when present.
    device = 'cpu'
    try:
        if torch.cuda.is_available():
            probe = torch.tensor([1.], device='cuda') + torch.tensor([1.], device='cuda')
            _ = probe.cpu()
            device = 'cuda'
    except Exception:
        # Some AMD/ROCm builds expose the device but lack a compatible kernel image
        # for small ops. Prompt work remains fully local and safely uses CPU.
        device = 'cpu'
    weights = torch.tensor([1., 1.1, 1., 1.2, 1.], device=device)
    scores = torch.sigmoid(weights).detach().cpu().tolist()
    additions = []
    for i, terms in enumerate(DOMAINS.values()):
        if not any(term.split()[0] in text.lower() for term in terms):
            additions.extend(terms[:2 if scores[i] > .7 else 1])
    enhanced = text + ', ' + ', '.join(additions)
    tips = ['Specify a color palette', 'Choose a pose or rotation', 'Add material language', 'Describe accessories', 'Choose low-poly or detailed geometry']
    return {'raw': raw, 'enhanced': enhanced, 'tips': tips, 'device': device, 'torch': torch.__version__, 'hip': torch.version.hip}

if __name__ == '__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('prompt', nargs='+'); ap.add_argument('--json', action='store_true'); a=ap.parse_args()
    result=compile_prompt(' '.join(a.prompt))
    print(json.dumps(result) if a.json else result['enhanced'])
