import sys, json, math
from shapely.geometry import Polygon, LineString, Point, box
from shapely.ops import unary_union
from shapely import affinity
P=json.load(open(sys.argv[1]))
def inter(p1,p2,p3,p4):
    x1,y1=p1;x2,y2=p2;x3,y3=p3;x4,y4=p4
    d=(x1-x2)*(y3-y4)-(y1-y2)*(x3-x4)
    t=((x1-x3)*(y3-y4)-(y1-y3)*(x3-x4))/d
    return (x1+t*(x2-x1),y1+t*(y2-y1))
# ---- ZAPATAS (esquinas leídas de capa ZAPATA; ver reporte) ----
Z={}
Z["Z1-a"]=("Z1",[(-14.774,-6.827),(-12.941,-8.045),(-11.724,-6.213),(-13.556,-4.995)])
Z["Z1-b"]=("Z1",[(-27.760,-6.558),(-28.289,-8.694),(-26.153,-9.223),(-25.624,-7.088)])
Z["Z1-c"]=("Z1",[(5.750,-6.685),(7.781,-7.532),(8.627,-5.501),(6.597,-4.655)])
Z["Z1-d"]=("Z1",[(9.772,2.960),(11.803,2.113),(12.650,4.143),(10.619,4.990)])
Z["Z1-e"]=("Z1",[(3.946,5.227),(6.254,4.265),(7.216,6.572),(4.909,7.534)])
Z["Z2"]=("Z2",[(-2.011,4.935),(1.889,4.935),(1.889,8.835),(-2.011,8.835)])
Z["Z3-a"]=("Z3",[(-18.660,4.720),(-15.360,4.720),(-15.360,8.020),(-18.660,8.020)])
Z["Z3-b"]=("Z3",[(-12.886,-0.317),(-9.586,-0.317),(-9.586,2.983),(-12.886,2.983)])
Z["Z3-c"]=("Z3",[(-11.354,-3.764),(-8.054,-3.764),(-8.054,-0.464),(-11.354,-0.464)])
Z["Z4"]=("Z4",[(-25.415,-4.015),(-26.799,-6.097),(-24.717,-7.481),(-23.333,-5.399)])
c1=inter((-16.351,-6.133),(-13.354,-8.126),(-13.104,-8.292),(-17.317,-14.637))
c3=inter((-13.104,-8.292),(-17.317,-14.637),(-17.647,-14.723),(-20.708,-12.688))
c4=inter((-17.647,-14.723),(-20.708,-12.688),(-18.761,-9.759),(-16.351,-6.133))
Z["Z5"]=("Z5",[(-16.351,-6.133),c1,c3,c4])
Z["Z6"]=("Z6",[(-22.475,-6.326),inter((-22.475,-6.326),(-23.247,-9.634),(-23.315,-9.926),(-20.597,-10.600)),
               inter((-23.315,-9.926),(-20.597,-10.600),(-19.675,-10.829),(-19.403,-9.693)),
               inter((-19.403,-9.693),(-18.797,-7.165),(-18.797,-7.165),(-20.339,-6.813))])
Z["Z7"]=("Z7",[(-22.232,1.496),(-24.059,-1.252),(-19.286,-4.425),(-17.459,-1.677)])
Z["Z8"]=("Z8",[(-4.659,-3.764),(1.889,-3.764),(1.889,3.329),(-4.659,3.329)])
zap={k:Polygon(v) for k,(t,v) in Z.items()}
ZU=unary_union(list(zap.values()))
# ---- tramos (pares de bordes) ----
def segs(lay,widths):
    out=[]
    for x in P[lay]:
        p,q=x["p"],x["q"]; out.append(dict(w=x["w"],d=x["d"],p=tuple(p),q=tuple(q)))
    return out
def merge(sg):
    # une piezas colineales del mismo ancho con hueco <=1.05
    changed=True
    while changed:
        changed=False
        for i in range(len(sg)):
            for j in range(i+1,len(sg)):
                a,b=sg[i],sg[j]
                if a["w"]!=b["w"]: continue
                ux,uy=a["q"][0]-a["p"][0],a["q"][1]-a["p"][1]; L=math.hypot(ux,uy); ux/=L; uy/=L
                vx,vy=b["q"][0]-b["p"][0],b["q"][1]-b["p"][1]; Lb=math.hypot(vx,vy)
                if abs(ux*vy-uy*vx)/Lb>0.01: continue
                off=lambda pt:(pt[0]-a["p"][0])*(-uy)+(pt[1]-a["p"][1])*ux
                if abs(off(b["p"]))>0.05 or abs(off(b["q"]))>0.05: continue
                t=lambda pt:(pt[0]-a["p"][0])*ux+(pt[1]-a["p"][1])*uy
                ts=sorted([(0,1),(L,1),(t(b["p"]),2),(t(b["q"]),2)])
                ia=(0,L); ib=sorted([t(b["p"]),t(b["q"])])
                gap=max(ib[0]-ia[1],ia[0]-ib[1])
                if gap>1.05: continue
                lo,hi=min(ia[0],ib[0]),max(ia[1],ib[1])
                sg[i]=dict(w=a["w"],d=max(a["d"],b["d"]),p=(a["p"][0]+ux*lo,a["p"][1]+uy*lo),q=(a["p"][0]+ux*hi,a["p"][1]+uy*hi))
                del sg[j]; changed=True; break
            if changed: break
    return sg
def rect(s,ext0=0,ext1=0):
    ux,uy=s["q"][0]-s["p"][0],s["q"][1]-s["p"][1]; L=math.hypot(ux,uy); ux/=L; uy/=L
    p=(s["p"][0]-ux*ext0,s["p"][1]-uy*ext0); q=(s["q"][0]+ux*ext1,s["q"][1]+uy*ext1)
    return LineString([p,q]).buffer(s["d"]/2,cap_style=2)
def extend(sg,others):
    for i,s in enumerate(sg):
        oth=unary_union([rect(o) for j,o in enumerate(sg) if j!=i]+others)
        ux,uy=s["q"][0]-s["p"][0],s["q"][1]-s["p"][1]; L=math.hypot(ux,uy); ux/=L; uy/=L
        ex=[0,0]
        for k,(pt,sx) in enumerate([(s["p"],-1),(s["q"],1)]):
            ray=LineString([pt,(pt[0]+sx*ux*1.2,pt[1]+sx*uy*1.2)])
            ins=ray.intersection(oth.buffer(0.01))
            if ins.is_empty: continue
            parts=[ins] if ins.geom_type=="LineString" else list(getattr(ins,"geoms",[]))
            for g in parts:
                if g.geom_type=="LineString" and Point(pt).distance(g)<0.06: ex[k]=min(g.length,1.2)
        s["ext"]=ex
    return sg
cim=segs("CIMIENTO 004",[0.7,1.0]); sa=segs("S-solera de amarre 003",[0.3])
mc=merge([s for s in cim if s["w"]==1.0]); cc=merge([s for s in cim if s["w"]==0.7])
rects_all=[rect(s) for s in mc+cc]
mc=extend(mc,[rect(s) for s in cc]); cc=extend(cc,[rect(s) for s in mc])
# parches manuales (juntas no cerradas por pares)
def foot(o,a,i):
    ux,uy=a[0]-o[0],a[1]-o[1]; L=math.hypot(ux,uy); ux/=L; uy/=L
    t=(i[0]-o[0])*ux+(i[1]-o[1])*uy; return (o[0]+ux*t,o[1]+uy*t)
def corner(o,a,b,i):  # esquina exterior o, bordes exteriores hacia a y b, esquina interior i
    return Polygon([o,foot(o,a,i),i,foot(o,b,i)])
PATCHES={
 "MC1 junta N (-11.4,8.0)":Polygon([(-11.79,7.04),(-11.09,7.04),(-11.09,8.84),(-11.61,8.84),(-11.61,8.04),(-11.79,8.04)]),
 "MC1 esquina NO (-19.2,8.0)":corner((-19.214,8.036),(-11.611,8.036),(-30.042,-8.259),(-18.660,7.036)),
 "MC1 esquina O (-30.0,-8.3)":corner((-30.042,-8.259),(-19.214,8.036),(-20.597,-10.600),(-28.424,-7.630)),
 "MC1 remate O junto a Z1 (-28.0,-7.2)":Polygon([(-27.79,-6.68),(-28.05,-7.72),(-28.42,-7.63)]),
 "MC1 esquina S (-18.0,-17.3)":corner((-17.967,-17.261),(-33.735,-13.353),(-17.318,-14.640),(-18.697,-16.050)),
 "MC1 junta SE de Z8 (1.9,-3.8)":Polygon([(1.889,-3.764),(1.739,-3.914),(1.739,-4.091),(1.754,-4.097),(2.139,-3.175),(2.139,-2.76),(1.889,-2.76)]),
 "MC1 junta NE de Z2 (2.1,6.8)":Polygon([(1.889,6.293),(2.139,6.293),(2.524,7.215),(1.889,7.480)]),
}
patch_mc=list(PATCHES.values())
MCU=unary_union([rect(s,*s["ext"]) for s in mc]+patch_mc)
PATCH_CC={"CC1 esquina E (3.7,0.8)":corner((3.70,0.81),(5.30,4.66),(2.14,0.81),(3.23,1.51))}
CCU=unary_union([rect(s,*s["ext"]) for s in cc]+list(PATCH_CC.values()))
MC_net=MCU.difference(ZU); CC_net=CCU.difference(MCU).difference(ZU)
CC_inZ8=CCU.difference(MCU).intersection(zap["Z8"]); MC_inZ=MCU.intersection(ZU); CC_inZ=CCU.difference(MCU).intersection(ZU)
SAU=unary_union([rect(s) for s in sa]); SA_net=SAU.difference(ZU)
# centerlines netas para DXF: recortar con prioridad (orden por longitud)
def centerlines(sg,block,w):
    out=[]; taken=block
    for s in sorted(sg,key=lambda s:-math.dist(s["p"],s["q"])):
        e=s.get("ext",[0,0]); ux,uy=s["q"][0]-s["p"][0],s["q"][1]-s["p"][1]; L=math.hypot(ux,uy); ux/=L; uy/=L
        ln=LineString([(s["p"][0]-ux*e[0],s["p"][1]-uy*e[0]),(s["q"][0]+ux*e[1],s["q"][1]+uy*e[1])])
        r=ln.difference(taken.buffer(-0.001) if not taken.is_empty else taken)
        parts=[r] if r.geom_type=="LineString" else list(getattr(r,"geoms",[]))
        for g in parts:
            if g.length>0.05: out.append(dict(coords=list(g.coords),L=g.length,w=s["d"]))
        taken=unary_union([taken,ln.buffer(s["d"]/2,cap_style=2)])
    return out
cl_mc=centerlines(mc,ZU,1.0)
cl_cc=centerlines(cc,unary_union([ZU,MCU]),0.7)
cl_sa=centerlines([dict(s,ext=[0,0]) for s in sa],ZU,0.3)
res=dict(patches={k:dict(area=v.area,pts=list(v.exterior.coords)) for k,v in list(PATCHES.items())+list(PATCH_CC.items())},
 MCnet=[list(g.exterior.coords) for g in (MC_net.geoms if MC_net.geom_type!='Polygon' else [MC_net])],
 CCnet=[list(g.exterior.coords) for g in (CC_net.geoms if CC_net.geom_type!='Polygon' else [CC_net])],
 SAnet=[list(g.exterior.coords) for g in (SA_net.geoms if SA_net.geom_type!='Polygon' else [SA_net])],
 SA_tramos=[dict(p=s['p'],q=s['q'],L=math.dist(s['p'],s['q'])) for s in sa],

 zap={k:dict(tipo=Z[k][0],pts=[list(p) for p in Z[k][1]],area=zap[k].area,
   lados=[math.dist(Z[k][1][i],Z[k][1][(i+1)%4]) for i in range(4)]) for k in Z},
 MC=dict(area=MC_net.area,L=MC_net.area/1.0,L_cl=sum(c["L"] for c in cl_mc),area_bajo_zap=MC_inZ.area,cl=cl_mc),
 CC=dict(area=CC_net.area,L=CC_net.area/0.7,L_cl=sum(c["L"] for c in cl_cc),area_bajo_zap=CC_inZ.area,area_en_Z8=CC_inZ8.area,cl=cl_cc),
 SA=dict(area=SA_net.area,L=SA_net.area/0.3,L_cl=sum(c["L"] for c in cl_sa),L_bruto=SAU.area/0.3,cl=cl_sa),
)
json.dump(res,open(sys.argv[2],"w"),default=float)
print("MC1: area neta %.3f m2  L=A/1.00 %.3f  L ejes %.3f  bajo zapatas %.3f m2"%(MC_net.area,MC_net.area,res["MC"]["L_cl"],MC_inZ.area))
print("CC1: area neta %.3f m2  L=A/0.70 %.3f  L ejes %.3f  bajo zap %.3f m2 (en Z8 %.3f m2 = %.2f ml)"%(CC_net.area,CC_net.area/0.7,res["CC"]["L_cl"],CC_inZ.area,CC_inZ8.area,CC_inZ8.area/0.7))
print("SA : area neta %.3f  L=A/0.30 %.3f  L ejes %.3f  bruto %.3f"%(SA_net.area,SA_net.area/0.3,res["SA"]["L_cl"],SAU.area/0.3))
for k,v in res["zap"].items(): print(k,v["tipo"],"A=%.3f"%v["area"],["%.3f"%l for l in v["lados"]])
# overlaps zapatas entre si
ks=list(zap)
for i in range(len(ks)):
    for j in range(i+1,len(ks)):
        a=zap[ks[i]].intersection(zap[ks[j]]).area
        if a>1e-4: print("TRASLAPE",ks[i],ks[j],round(a,3))
# diagnostico CC
CLB=unary_union([LineString(c["coords"]).buffer(0.35,cap_style=2) for c in cl_cc])
dif=CC_net.difference(CLB)
for g in ([dif] if dif.geom_type=="Polygon" else list(dif.geoms)):
    if g.area>0.02: c=g.representative_point(); print("CC area sin eje: %.3f en (%.2f,%.2f)"%(g.area,c.x,c.y))
dif2=CLB.difference(CC_net)
for g in ([dif2] if dif2.geom_type=="Polygon" else list(dif2.geoms)):
    if g.area>0.02: c=g.representative_point(); print("eje sin area: %.3f en (%.2f,%.2f)"%(g.area,c.x,c.y))
# figura de verificacion
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fig,ax=plt.subplots(figsize=(30,18),dpi=80)
def fill(g,c,a=0.5):
    for pg in ([g] if g.geom_type=="Polygon" else list(g.geoms)):
        if pg.geom_type!="Polygon": continue
        ax.fill(*pg.exterior.xy,color=c,alpha=a,lw=0)
        for h in pg.interiors: ax.fill(*h.xy,color="white")
for k,p in zap.items(): fill(p,"magenta",0.35); ax.text(p.centroid.x,p.centroid.y,k,fontsize=12,weight="bold")
fill(MC_net,"red"); fill(CC_net,"blue"); fill(SA_net,"green")
import ezdxf
from ezdxf import recover
d,_=recover.readfile(sys.argv[3]); 
for e in d.modelspace():
    if e.dxf.layer in ("CIMIENTO 004","ZAPATA"):
        if e.dxftype()=="LINE": ax.plot([e.dxf.start.x,e.dxf.end.x],[e.dxf.start.y,e.dxf.end.y],"k",lw=0.6)
        elif e.dxftype()=="LWPOLYLINE":
            p=[q[:2] for q in e.get_points()]+([e.get_points()[0][:2]] if e.closed else []); ax.plot([a[0] for a in p],[a[1] for a in p],"k",lw=0.6)
ax.set_aspect("equal"); fig.savefig(sys.argv[4],bbox_inches="tight")
