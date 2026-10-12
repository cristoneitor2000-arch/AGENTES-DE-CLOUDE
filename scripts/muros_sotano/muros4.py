import sys, json, math, collections, ezdxf
from ezdxf import recover
W=json.load(open(sys.argv[1])); src=sys.argv[2]
# 1) unir 13+14 (doble hilada mal agrupada)
def off(a,b):
    ux,uy=(a["q"][0]-a["p"][0])/a["L"],(a["q"][1]-a["p"][1])/a["L"]
    return abs((b["p"][0]-a["p"][0])*(-uy)+(b["p"][1]-a["p"][1])*ux)
a,b=W[13],W[14]; assert abs(a["ang"]-b["ang"])<0.5 and off(a,b)<0.2
m=dict(a); m["p"]=((a["p"][0]+b["p"][0])/2,(a["p"][1]+b["p"][1])/2); m["q"]=((a["q"][0]+b["q"][0])/2,(a["q"][1]+b["q"][1])/2)
m["L"]=math.dist(m["p"],m["q"]); m["e"]=round(off(a,b)+0.15,3); m["n"]=a["n"]+b["n"]
W=[w for i,w in enumerate(W) if i not in (13,14)]+[m]
# 2) etiquetas M cercanas
doc,_=recover.readfile(src); msp=doc.modelspace()
labs=[(t.dxf.text,(t.dxf.insert.x,t.dxf.insert.y)) for t in msp.query("TEXT") if t.dxf.text.startswith("M") and not t.dxf.text.startswith("MC")]
from shapely.geometry import LineString, Point
for w in W:
    ln=LineString([w["p"],w["q"]]); best=sorted(labs,key=lambda l:ln.distance(Point(l[1])))
    w["etq"]=best[0][0] if ln.distance(Point(best[0][1]))<0.9 else ""
# 3) grupo y tipo
for w in W:
    w["grupo"]="MC" if w["e"]>=0.29 else "ED"
    if w["grupo"]=="MC": w["tipo"]="Muro MC1 block doble hilada 0.15+0.15"
    elif w["cls"]=="C": w["tipo"]="Muro block %.2f que carga"%w["e"]
    else: w["tipo"]="Muro block %.2f que no carga"%w["e"]
# 4-5) hueco al siguiente tramo colineal (solo el más cercano)
V=[];H=[]
for a in W:
    ux,uy=(a["q"][0]-a["p"][0])/a["L"],(a["q"][1]-a["p"][1])/a["L"]
    t=lambda pt:(pt[0]-a["p"][0])*ux+(pt[1]-a["p"][1])*uy
    best=None
    for b in W:
        if a is b or abs(a["ang"]-b["ang"])>0.5 or off(a,b)>0.08: continue
        g=min(t(b["p"]),t(b["q"]))-a["L"]
        if g>=0.10 and (best is None or g<best[0]): best=(g,b)
    if not best: continue
    g,b=best; c=(a["p"][0]+ux*(a["L"]+g/2),a["p"][1]+uy*(a["L"]+g/2))
    if a["grupo"]=="ED" and b["grupo"]=="ED" and a["cls"]==b["cls"] and abs(a["e"]-b["e"])<0.01 and 0.55<=g<=2.5:
        V.append(dict(a=a["id"],b=b["id"],ancho=round(g,3),c=c,ang=a["ang"],e=a["e"],cls=a["cls"]))
    elif g<=0.85 and a["grupo"]==b["grupo"]:
        H.append(dict(a=a["id"],b=b["id"],g=round(g,3),c=c))
for k,v in enumerate(V,1): v["id"]=f"V-{k:02d}"
W.sort(key=lambda w:(w["grupo"]!="MC",w["tipo"],-w["L"]))
for k,w in enumerate(W,1): w["wid"]=("MC-" if w["grupo"]=="MC" else "M-")+f"{k:02d}"
idmap={w["id"]:w["wid"] for w in W}
for v in V: v["a"]=idmap[v["a"]]; v["b"]=idmap[v["b"]]
for h in H: h["a"]=idmap[h["a"]]; h["b"]=idmap[h["b"]]
tot=collections.defaultdict(float)
for w in W: tot[w["tipo"]]+=w["L"]
for k,v in tot.items(): print(f"{k:45s} {v:7.2f} ml")
print("vanos:",[(v["id"],v["ancho"],v["a"],v["b"]) for v in V])
print("huecos mocheta/columna:",len(H),[(h["a"],h["b"],h["g"]) for h in H])
json.dump(dict(W=W,V=V,H=H),open(sys.argv[3],"w"))
