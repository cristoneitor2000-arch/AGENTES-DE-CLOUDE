import sys, json, math, ezdxf
from ezdxf import recover
from ezdxf.enums import TextEntityAlignment
src,resf,out=sys.argv[1:4]
R=json.load(open(resf))
doc,aud=recover.readfile(src); msp=doc.modelspace()
# 1) capa 00 con todo el plano original
if "00" not in doc.layers: doc.layers.add("00",color=8)
borr=0
for e in list(msp):
    if e.dxftype()=="LWPOLYLINE":
        pts=e.get_points()
        if len(pts)<2 or sum(math.dist(pts[i][:2],pts[i+1][:2]) for i in range(len(pts)-1))<1e-6:
            msp.delete_entity(e); borr+=1; continue
    e.dxf.layer="00"
# 2) capas de cuantificación (jerarquía en el nombre)
L={
 "CC1":"CUANT-CIMENTACION-CIMIENTO CORRIDO CC1 0.70",
 "CC1H":"CUANT-CIMENTACION-CIMIENTO CORRIDO CC1 0.70 HUELLA",
 "SA":"CUANT-CIMENTACION-SOLERA SA 0.30",
 "SAH":"CUANT-CIMENTACION-SOLERA SA 0.30 HUELLA NETA",
 "MC1":"CUANT-MURO CONTENCION-CIMIENTO MC1 1.00",
 "MC1H":"CUANT-MURO CONTENCION-CIMIENTO MC1 1.00 HUELLA",
}
col={"CC1":5,"CC1H":5,"SA":3,"SAH":3,"MC1":1,"MC1H":1}
for k,n in L.items(): doc.layers.add(n,color=col[k])
tipos=sorted({v["tipo"] for v in R["zap"].values()})
for t in tipos: doc.layers.add(f"CUANT-CIMENTACION-ZAPATAS-{t}",color=6)
# 3) bloques de zapata con atributos (doble clic = EATTEDIT)
def dims(v):
    l=v["lados"]; return (l[0]+l[2])/2,(l[1]+l[3])/2
made=set()
for k,v in R["zap"].items():
    a,b=dims(v); bn=f"ZAP_{v['tipo']}_{a:.2f}x{b:.2f}"
    if bn not in made:
        blk=doc.blocks.new(bn); made.add(bn)
        blk.add_lwpolyline([(-a/2,-b/2),(a/2,-b/2),(a/2,b/2),(-a/2,b/2)],close=True,dxfattribs={"layer":"0","color":0})
        blk.add_line((-a/2,-b/2),(a/2,b/2),dxfattribs={"layer":"0","color":0}); blk.add_line((-a/2,b/2),(a/2,-b/2),dxfattribs={"layer":"0","color":0})
        for i,(tag,pr,dv) in enumerate([("ID","ID","") ,("TIPO","Tipo",v["tipo"]),("LARGO","Largo (m)",f"{a:.2f}"),("ANCHO","Ancho (m)",f"{b:.2f}"),("PERALTE","Peralte (m)","PEND")]):
            ad=blk.add_attdef(tag,insert=(0,0.25-0.2*i),text=dv,height=0.12,dxfattribs={"prompt":pr,"layer":"0","color":0})
            ad.set_placement((0,0.25-0.2*i),align=TextEntityAlignment.MIDDLE_CENTER)
    p=v["pts"]; cx=sum(q[0] for q in p)/4; cy=sum(q[1] for q in p)/4
    ang=math.degrees(math.atan2(p[1][1]-p[0][1],p[1][0]-p[0][0]))
    ins=msp.add_blockref(bn,(cx,cy),dxfattribs={"layer":f"CUANT-CIMENTACION-ZAPATAS-{v['tipo']}","rotation":ang})
    ins.add_auto_attribs({"ID":k,"TIPO":v["tipo"],"LARGO":f"{a:.2f}","ANCHO":f"{b:.2f}","PERALTE":"PEND"})
# 4) cimientos: ejes (polilíneas abiertas) y huellas netas (cerradas)
for key,lay in [("MC","MC1"),("CC","CC1")]:
    for c in R[key]["cl"]:
        msp.add_lwpolyline([tuple(x[:2]) for x in c["coords"]],dxfattribs={"layer":L[lay],"const_width":0.0})
for key,lay in [("MCnet","MC1H"),("CCnet","CC1H"),("SAnet","SAH")]:
    for ring in R[key]:
        h=msp.add_hatch(color=256,dxfattribs={"layer":L[lay]}); h.set_pattern_fill("ANSI31",scale=0.3); h.paths.add_polyline_path([tuple(x[:2]) for x in ring],is_closed=True)
        msp.add_lwpolyline([tuple(x[:2]) for x in ring],close=True,dxfattribs={"layer":L[lay]})
for t in R["SA_tramos"]:
    msp.add_lwpolyline([tuple(t["p"]),tuple(t["q"])],dxfattribs={"layer":L["SA"]})
# 5) bloquear todo menos 0 y CUANT-*
for ly in doc.layers:
    n=ly.dxf.name
    if n=="0" or n.startswith("CUANT-"): ly.unlock(); ly.on(); ly.thaw()
    else: ly.lock()
doc.header["$CLAYER"]="0"
# 6) orden de dibujo: la cuantificación se agregó al final (queda encima); se envía 00 atrás con SORTENTS
handles=[e.dxf.handle for e in msp]
quant=[e for e in msp if e.dxf.layer.startswith("CUANT-")]
base=[e for e in msp if not e.dxf.layer.startswith("CUANT-")]
order={}
i=1
for e in base: order[e.dxf.handle]=f"{i:X}"; i+=1
for e in quant: order[e.dxf.handle]=f"{i:X}"; i+=1
msp.set_redraw_order(order)
au=doc.audit()
doc.saveas(out)
print("borradas polilíneas nulas:",borr,"| audit errores:",len(au.errors),"fixes:",len(au.fixes),"| bloques zapata:",len(made),"| ent cuant:",len(quant))
