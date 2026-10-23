import json,subprocess,shutil,sys,tempfile,xml.etree.ElementTree as ET
from pathlib import Path
D=Path(sys.argv[1]);PY=sys.argv[2];pred=json.loads((D/"expected/predicted-sweep.json").read_text())
V,P=pred["victim"],pred["polluter"]
def run(work,args):
    x=work/"r.xml";subprocess.run([PY,"-m","pytest","-q","-p","no:cacheprovider","--junitxml",str(x),*args],cwd=work,capture_output=True)
    st={}
    for tc in ET.parse(x).iter("testcase"):
        nid=tc.get("classname").replace(".","/")+".py::"+tc.get("name")
        st[nid]="failed" if tc.find("failure") is not None or tc.find("error") is not None else "passed"
    return st
out={}
for v in ("prefix","wrong_fix","real_fix"):
    w=Path(tempfile.mkdtemp());shutil.copytree(D/"sample",w,dirs_exist_ok=True);shutil.copy(D/f"fixes/test_cart.{v}.py",w/"tests/test_cart.py")
    plain=[run(w,[])[V] for _ in range(3)]
    rep=[run(w,[P,V])[V] for _ in range(3)]
    sw=[int(s) for s,o in pred["orders"].items() if run(w,o)[V]=="failed"]
    pol=all(run(w,o)[P]=="passed" for o in list(pred["orders"].values())[:5])
    out[v]=(plain,rep,sorted(sw)==(pred["victim_fails"] if v!="real_fix" else []),len(sw),pol)
    print(v,out[v])
