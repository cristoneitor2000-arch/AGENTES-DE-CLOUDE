import sys, ezdxf, collections, math, json
from ezdxf import recover, bbox
from shapely.geometry import Polygon
from shapely.ops import unary_union
doc,_=recover.readfile(sys.argv[1]); msp=doc.modelspace()
def eff(i):
    b=doc.blocks.get(i.dxf.name)
    if b and b.block_record.has_xdata("AcDbBlockRepBTag"):
        r=doc.entitydb.get(b.block_record.get_xdata("AcDbBlockRepBTag")[1].value)
        if r: return r.dxf.name
    return i.dxf.name
units=[]
for i in msp.query("INSERT"):
    if i.dxf.layer not in ("BLOCK251","BLOKS 008","block 008","block0.14"): continue
    b=doc.blocks.get(i.dxf.name); bb=bbox.extents(b,fast=True)
    m=i.matrix44()
    pts=[m.transform((x,y,0)) for x,y in [(bb.extmin.x,bb.extmin.y),(bb.extmax.x,bb.extmin.y),(bb.extmax.x,bb.extmax.y),(bb.extmin.x,bb.extmax.y)]]
    pg=Polygon([(p.x,p.y) for p in pts])
    a=math.dist((pts[0].x,pts[0].y),(pts[1].x,pts[1].y)); c=math.dist((pts[1].x,pts[1].y),(pts[2].x,pts[2].y))
    units.append(dict(layer=i.dxf.layer,name=eff(i),poly=[(p.x,p.y) for p in pts],w=round(min(a,c),3),l=round(max(a,c),3),h=i.dxf.handle))
print(len(units)); print(collections.Counter((u["layer"],u["name"],u["w"],u["l"]) for u in units))
json.dump(units,open(sys.argv[2],"w"))
