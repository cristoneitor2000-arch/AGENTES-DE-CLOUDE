import sys, json, math, collections, ezdxf
from ezdxf import recover
from ezdxf.enums import TextEntityAlignment
D=json.load(open(sys.argv[1])); src,outdxf,outx=sys.argv[2:5]
W,V,H=D["W"],D["V"],D["H"]
# verificación independiente: área de unidades / espesor
chk=collections.defaultdict(lambda:[0,0])
for w in W: chk[w["tipo"]][0]+=w["L"]; chk[w["tipo"]][1]+=w["n"]*0.40*w["w"][0]/w["e"]
print("Verificación (eje vs unidades×0.40×ancho/espesor):")
for k,(a,b) in chk.items(): print(f"  {k:42s} eje={a:7.2f}  unidades={b:7.2f}  Δ={100*(a-b)/b:+.1f}%")
# tramos sobre vanos (muro continuo a altura total)
WV=[]
for v in V:
    a=next(w for w in W if w["wid"]==v["a"]); ux,uy=(a["q"][0]-a["p"][0])/a["L"],(a["q"][1]-a["p"][1])/a["L"]
    p=(a["q"][0],a["q"][1]); q=(p[0]+ux*v["ancho"],p[1]+uy*v["ancho"])
    WV.append(dict(wid=a["wid"]+"/"+v["id"],tipo=a["tipo"],grupo=a["grupo"],e=a["e"],p=p,q=q,L=v["ancho"],etq=a["etq"],vano=v["id"],cls=a["cls"],ang=a["ang"]))
ALL=W+WV
# ---------- DXF ----------
doc,_=recover.readfile(src); msp=doc.modelspace()
if "00" not in doc.layers: doc.layers.add("00",color=8)
for e in list(msp):
    if e.dxftype()=="LWPOLYLINE":
        pts=e.get_points()
        if len(pts)<2 or sum(math.dist(pts[i][:2],pts[i+1][:2]) for i in range(len(pts)-1))<1e-6: msp.delete_entity(e); continue
    e.dxf.layer="00"
LAY={"Muro MC1 block doble hilada 0.15+0.15":("CUANT-MURO CONTENCION-MURO MC1 BLOCK 0.30",1),
     "Muro block 0.15 que carga":("CUANT-MUROS-BLOCK 0.15 CARGA",5),"Muro block 0.20 que carga":("CUANT-MUROS-BLOCK 0.20 CARGA",4),
     "Muro block 0.15 que no carga":("CUANT-MUROS-BLOCK 0.15 NO CARGA",3)}
for n,c in LAY.values(): doc.layers.add(n,color=c)
doc.layers.add("CUANT-MUROS-VANOS",color=2)
for w in ALL:
    bn="MURO_"+w["wid"].replace("/","_")
    blk=doc.blocks.new(bn); L=w["L"]; e=w["e"]
    blk.add_lwpolyline([(0,-e/2),(L,-e/2),(L,e/2),(0,e/2)],close=True,dxfattribs={"layer":"0","color":0})
    blk.add_line((0,0),(L,0),dxfattribs={"layer":"0","color":0,"linetype":"CONTINUOUS"})
    vals=[("ID","ID",w["wid"]),("TIPO","Tipo",w["tipo"]),("ETQ","Etiqueta plano",w.get("etq","")),("EJE_L","Longitud eje (m)",f"{L:.2f}"),("ESPESOR","Espesor (m)",f"{e:.2f}"),("ALTURA","Altura total (m)","PEND"),("VANO","Vano",w.get("vano",""))]
    for i,(tag,pr,dv) in enumerate(vals):
        ad=blk.add_attdef(tag,insert=(L/2,0),text=dv,height=0.08,dxfattribs={"prompt":pr,"layer":"0","color":0})
        ad.set_placement((L/2,0.05-0.0*i),align=TextEntityAlignment.MIDDLE_CENTER)
        if tag!="ID": ad.is_invisible=True
    lay="CUANT-MUROS-VANOS" if w.get("vano") else LAY[w["tipo"]][0]
    ref=msp.add_blockref(bn,w["p"],dxfattribs={"layer":lay,"rotation":math.degrees(math.atan2(w["q"][1]-w["p"][1],w["q"][0]-w["p"][0]))})
    ref.add_auto_attribs({t:v for t,_,v in vals})
for ly in doc.layers:
    n=ly.dxf.name
    if n=="0" or n.startswith("CUANT-"): ly.unlock(); ly.on(); ly.thaw()
    else: ly.lock()
doc.header["$CLAYER"]="0"
base=[e for e in msp if not e.dxf.layer.startswith("CUANT-")]; quant=[e for e in msp if e.dxf.layer.startswith("CUANT-")]
msp.set_redraw_order({e.dxf.handle:f"{i:X}" for i,e in enumerate(base+quant,1)})
au=doc.audit(); doc.saveas(outdxf); print("DXF audit errores:",len(au.errors),"bloques muro:",len(ALL))
json.dump(dict(ALL=ALL,V=V,H=H,chk={k:v for k,v in chk.items()}),open(sys.argv[5],"w"))
