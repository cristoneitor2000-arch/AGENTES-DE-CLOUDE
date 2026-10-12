import sys, ezdxf, math, json
from ezdxf import recover
doc, aud = recover.readfile(sys.argv[1]); msp=doc.modelspace()
def segs(layer):
    out=[]
    for e in msp:
        if e.dxf.layer!=layer: continue
        if e.dxftype()=="LINE": out.append(((e.dxf.start.x,e.dxf.start.y),(e.dxf.end.x,e.dxf.end.y),e.dxf.handle))
        elif e.dxftype()=="LWPOLYLINE":
            p=[q[:2] for q in e.get_points()]
            if e.closed: p.append(p[0])
            for a,b in zip(p,p[1:]):
                if math.dist(a,b)>1e-4: out.append((a,b,e.dxf.handle))
    return out
def pair(sg, widths, tol=0.03):
    res=[]
    for i in range(len(sg)):
        a0,a1,ha=sg[i]; dx,dy=a1[0]-a0[0],a1[1]-a0[1]; La=math.hypot(dx,dy); ux,uy=dx/La,dy/La
        for j in range(i+1,len(sg)):
            b0,b1,hb=sg[j]; ex,ey=b1[0]-b0[0],b1[1]-b0[1]; Lb=math.hypot(ex,ey)
            if abs(ux*ey-uy*ex)/Lb>0.01: continue
            d=(b0[0]-a0[0])*(-uy)+(b0[1]-a0[1])*ux
            w=next((W for W in widths if abs(abs(d)-W)<tol),None)
            if w is None: continue
            ta=(0,La); tb=sorted([(b0[0]-a0[0])*ux+(b0[1]-a0[1])*uy,(b1[0]-a0[0])*ux+(b1[1]-a0[1])*uy])
            s,t=max(ta[0],tb[0]),min(ta[1],tb[1])
            if t-s<0.15: continue
            nx,ny=-uy*d/2,ux*d/2
            p=(a0[0]+ux*s+nx,a0[1]+uy*s+ny); q=(a0[0]+ux*t+nx,a0[1]+uy*t+ny)
            res.append(dict(w=w,p=p,q=q,L=t-s,d=abs(d),ha=ha,hb=hb))
    return res
out={}
for lay,W in [("CIMIENTO 004",[0.70,1.00]),("S-solera de amarre 003",[0.30,0.25])]:
    r=pair(segs(lay),W); out[lay]=r
    print(lay,len(r))
    for x in r: print(f"  w={x['w']:.2f} d={x['d']:.3f} L={x['L']:6.3f} p=({x['p'][0]:.2f},{x['p'][1]:.2f}) q=({x['q'][0]:.2f},{x['q'][1]:.2f})")
json.dump(out,open(sys.argv[2],"w"))
# unpaired report
import itertools
for lay,W in [("CIMIENTO 004",[0.70,1.00]),("S-solera de amarre 003",[0.30])]:
    sg=segs(lay); r=pair(sg,W,0.03)
    print("== sin pareja",lay)
    for a,b,h in sg:
        L=math.dist(a,b)
        if L<0.3: continue
        # find any parallel neighbor within 1.5
        dx,dy=(b[0]-a[0])/L,(b[1]-a[1])/L; best=[]
        for c,d,h2 in sg:
            L2=math.dist(c,d)
            if L2<1e-6 or (c,d)==(a,b): continue
            if abs(dx*(d[1]-c[1])-dy*(d[0]-c[0]))/L2>0.01: continue
            off=(c[0]-a[0])*(-dy)+(c[1]-a[1])*dx
            ta=sorted([(c[0]-a[0])*dx+(c[1]-a[1])*dy,(d[0]-a[0])*dx+(d[1]-a[1])*dy])
            if min(L,ta[1])-max(0,ta[0])>0.15 and 0.05<abs(off)<1.6: best.append(round(abs(off),3))
        used=any(abs(x["L"])>0 and (x["ha"]==h or x["hb"]==h) for x in r)
        print(f"  L={L:6.2f} ({a[0]:.2f},{a[1]:.2f})-({b[0]:.2f},{b[1]:.2f}) offs={sorted(set(best))}")
