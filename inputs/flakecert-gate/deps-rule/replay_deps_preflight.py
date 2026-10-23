import csv, json, subprocess, sys, os, re
ROWS=list(csv.DictReader(open('../inputs/frozen-set.csv')))
MANIFEST_ORDER=['requirements.txt','requirements-dev.txt','requirements_dev.txt','setup.py','setup.cfg','pyproject.toml','tox.ini','pytest.ini','environment.yml','Pipfile']
CAP=int(os.environ.get("CAP","4"))
def tree(fid, repo, sha):
    os.makedirs('trees',exist_ok=True); fn=f'trees/{fid}.json'
    if not os.path.exists(fn) or 'tree' not in json.load(open(fn)):
        out=subprocess.run(['curl','-sL',f'https://api.github.com/repos/{repo}/git/trees/{sha}?recursive=1'],capture_output=True,text=True).stdout
        open(fn,'w').write(out)
    d=json.load(open(fn))
    assert 'tree' in d and not d.get('truncated'), (fid, str(d)[:200])
    return [t['path'] for t in d['tree'] if t['type']=='blob']
def line(r):
    repo=r['project_url'].split('github.com/')[1]
    paths=tree(r['id'],repo,r['sha'])
    root=set(p for p in paths if '/' not in p)
    man=[m for m in MANIFEST_ORDER if m in root]
    req=sorted(p for p in paths if p.endswith('.txt') and 'requirements' in p)[:CAP]
    return f"{r['id']} {r['role']} {repo} manifests: {man} req files: {req} "
log=[l.rstrip('\n') for l in open('../inputs/deps-preflight.log')][1:]
ok=0
for r,exp in zip(ROWS,log):
    got=line(r)
    if got.rstrip()==exp.rstrip(): ok+=1
    else: print('DIFF',r['id'],'\n exp',exp,'\n got',got)
print(f'match {ok}/{len(log)}')
