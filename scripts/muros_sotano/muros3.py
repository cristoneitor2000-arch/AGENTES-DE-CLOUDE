import sys, json, math, collections
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union
U=json.load(open(sys.argv[1])); R=json.load(open(sys.argv[2]))
CL={"BLOCK251":"C","block0.14":"C","block 008":"N","BLOKS 008":"N"}
for u in U:
    p=u["poly"]; a=math.dist(p[0],p[1]); b=math.dist(p[1],p[2])
    v=(p[1][0]-p[0][0],p[1][1]-p[0][1]) if a>=b else (p[2][0]-p[1][0],p[2][1]-p[1][1])
    L=math.hypot(*v); ang=math.degrees(math.atan2(v[1],v[0]))%180
    u["ang"]=ang; u["c"]=(sum(q[0] for q in p)/4,sum(q[1] for q in p)/4); u["cls"]=CL[u["layer"]]
# cluster por dirección y línea
lines=[]
for u in sorted(U,key=lambda u:u["ang"]):
    th=math.radians(u["ang"]); ux,uy=math.cos(th),math.sin(th)
    for Lc in lines:
        dang=min(abs(Lc["ang"]-u["ang"]),180-abs(Lc["ang"]-u["ang"]))
        if dang>1.5 or Lc["cls"]!=u["cls"]: continue
        off=(u["c"][0]-Lc["o"][0])*(-Lc["uy"])+(u["c"][1]-Lc["o"][1])*Lc["ux"]
        if abs(off)<=0.2: Lc["u"].append(u); break
    else:
        lines.append(dict(ang=u["ang"],ux=ux,uy=uy,o=u["c"],cls=u["cls"],u=[u]))
MCU=None
from shapely.geometry import shape
mcpolys=[Polygon(r) for r in R["MCnet"]]
zp=[Polygon(v["pts"]) for v in R["zap"].values()]
MC=unary_union(mcpolys+[Polygon(v["pts"]) for v in R["zap"].values()]).buffer(0.05)  # huella MC1 (+ zapatas que la interrumpen)
MCb=unary_union([Polygon(r) for r in R["MCnet"]]).buffer(0.30)
walls=[]
for Lc in lines:
    ux,uy=Lc["ux"],Lc["uy"]; o=Lc["o"]
    items=[]
    for u in Lc["u"]:
        t=[(q[0]-o[0])*ux+(q[1]-o[1])*uy for q in u["poly"]]; off=[(q[0]-o[0])*(-uy)+(q[1]-o[1])*ux for q in u["poly"]]
        items.append((min(t),max(t),min(off),max(off),u))
    items.sort(key=lambda x:x[0])
    seg=[]; cur=None
    for it in items:
        if cur and it[0]<=cur["t1"]+0.06: cur["t1"]=max(cur["t1"],it[1]); cur["o0"]=min(cur["o0"],it[2]); cur["o1"]=max(cur["o1"],it[3]); cur["n"]+=1; cur["w"].add(it[4]["w"])
        else:
            cur=dict(t0=it[0],t1=it[1],o0=it[2],o1=it[3],n=1,w={it[4]["w"]}); seg.append(cur)
    for i,s in enumerate(seg):
        om=(s["o0"]+s["o1"])/2; e=s["o1"]-s["o0"]
        p=(o[0]+ux*s["t0"]-uy*om,o[1]+uy*s["t0"]+ux*om); q=(o[0]+ux*s["t1"]-uy*om,o[1]+uy*s["t1"]+ux*om)
        mid=((p[0]+q[0])/2,(p[1]+q[1])/2)
        enMC=LineString([p,q]).intersection(MCb).length/math.dist(p,q)
        walls.append(dict(cls=Lc["cls"],p=p,q=q,L=math.dist(p,q),e=round(e,3),n=s["n"],w=sorted(s["w"]),ang=Lc["ang"],mc=enMC,line=id(Lc),gap_next=(seg[i+1]["t0"]-s["t1"]) if i+1<len(seg) else None))
walls.sort(key=lambda w:(w["cls"],-w["L"]))
tot=collections.defaultdict(float)
for i,w in enumerate(walls):
    w["id"]=i
    g=f"{w['gap_next']:.2f}" if w["gap_next"] is not None else "-"
    print(f"{i:3d} {w['cls']} e={w['e']:.2f} w={w['w']} L={w['L']:6.2f} n={w['n']:3d} MC={w['mc']:.2f} ang={w['ang']:6.1f} p=({w['p'][0]:.2f},{w['p'][1]:.2f}) q=({w['q'][0]:.2f},{w['q'][1]:.2f}) gap_sig={g}")
    tot[(w["cls"],w["e"],w["mc"]>0.5)]+=w["L"]
for k,v in sorted(tot.items()): print(k,round(v,2))
json.dump(walls,open(sys.argv[3],"w"))
