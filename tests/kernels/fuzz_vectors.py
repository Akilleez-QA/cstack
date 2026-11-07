"""Seeded random arguments for the differential: every tool, bad types, units, atmospheres and policy points."""
import json
import math
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[2]
r = random.Random(11)
FL=["NH3","nh3"," R-717 ","r717","ammonia","CO2","co2","r744","carbon dioxide","R134a","HFC-134a","r290","propane","R22","HCFC 22","R404A","R410A","R507A","R448A","(r-448a)","water",7,None,True,[],{}, "x"*65,"R_4_0_4_A"]
TU=["degC","degF","K","degR"]; PU=["kPa(a)","kPa(g)","psia","psig","bar(a)","bar(g)"]
def num():
    k=r.random()
    if k<.5: return r.uniform(-80,110)
    if k<.6: return round(r.uniform(-80,110),2)
    if k<.7: return float(r.randint(-100,200))
    if k<.8: return r.randint(-100,200)
    if k<.85: return r.choice([0,0.0,-0.0,1e9,-1e9,1000000001,1e-9,-1e-9,5e-324,1e-5,273.15,-273.15,-273.16,459.67,-459.67,-459.68,0.03125,0.09375,-0.03125,0.0078125])
    return r.uniform(0,6000)
def bad():
    return r.choice([None,True,False,"5",[],{}, [1], {"a":1}])
def tq():
    u=r.choice(TU)
    if r.random()<.6:
        c=r.uniform(-80,110); v={"degC":c,"degF":c*1.8+32,"K":c+273.15,"degR":(c+273.15)*1.8}[u]
    else: v=num()
    q={"value":v,"unit":u}
    return mut(q,["value","unit"],TU)
def pq():
    u=r.choice(PU)
    k=10**r.uniform(-1,4.2)
    v={"kPa(a)":k,"kPa(g)":k-101.325,"psia":k/6.89475,"psig":(k-101.325)/6.89475,"bar(a)":k/100,"bar(g)":(k-101.325)/100}[u]
    if r.random()<.1: v=num()
    return mut({"value":v,"unit":u},["value","unit"],PU)
def mut(q,keys,units,p=.08):
    if r.random()<p:
        q=dict(q); c=r.randint(0,5)
        if c==0: q["value"]=bad()
        elif c==1: q["unit"]=r.choice(["furlong",5,None,[],units[0]+" "])
        elif c==2: q.pop(r.choice(keys))
        elif c==3: q["extra"]=1
        elif c==4: return r.choice([5,"5",None,[]])
        else: q["value"]=r.choice([1e10,-1e10,1e308,10**30])
    return q
def atm():
    k=r.random()
    if k<.4: return None
    if k<.5: return {"basis":"standard"}
    if k<.75: return {"basis":"elevation","elevation":mut({"value":r.uniform(-600,6500) if r.random()<.8 else r.uniform(-2000,21000),"unit":r.choice(["m","ft"])},["value","unit"],["m","ft"])}
    if k<.92: return {"basis":"measured","pressure":mut(r.choice([{"value":r.uniform(35,115),"unit":"kPa(a)"},{"value":r.uniform(5,17),"unit":"psia"},{"value":r.uniform(.35,1.15),"unit":"bar(a)"}]),["value","unit"],["kPa(a)"])}
    return r.choice([{"basis":"standard","x":1},{"basis":"other"},"standard",5,[],{},{"basis":None},{"basis":["standard"]},{"basis":"elevation"},{"basis":"measured"},{"basis":"elevation","elevation":5},{"basis":"measured","pressure":{"value":100,"unit":"psig"}}])
def opt(a,**kw):
    for k,v in kw.items():
        if v is not None: a[k]=v
    return a
def side():
    return r.choice([None,None,"bubble","dew","bubble","dew","wet",5,[],"Dew"," dew"]) 
def fuzz_extra(a):
    if r.random()<.04: a=dict(a); a[r.choice(["extra","zz","aa"])]=1
    if r.random()<.04 and isinstance(a,dict) and a: a=dict(a); a.pop(r.choice(list(a)))
    return a
POINT={"label":"site alarm","concentration":{"value":10,"unit":"ppm"},"set_by":"plant manager","scope":"plant","reason":"site rule"}
def pol():
    p=dict(POINT); k=r.randint(0,17)
    if k==1: p["concentration"]={"value":r.choice([10.0,12.5,0,0.0,1e-5,1e9,0.1,1e-4,123456.789,1.5e-7]),"unit":"ppm"}
    if k==2: p["label"]=r.choice(["OSHA PEL","osha","my_limit","limits ok","no-limit","cal/osha","calosha x","x"*121,"x"*120,"\t","a\x1cb","\x1c","relx","PEL2","pel-2",5,None])
    if k==3: p["scope"]=r.choice(["world",5,None,"client","expression"])
    if k==4: p["set_by"]=r.choice([""," ",5,None,"\x1f","x"*2048,"x"*2049,"x"*300])
    if k==5: p["reason"]=r.choice([""," ",5,None,"\x85".encode().decode() if False else "\x1e","x"*2049,"y"*2048])
    if k==6: p["concentration"]=r.choice([5,"5",None,{"value":-1,"unit":"ppm"},{"value":1,"unit":"ppb"},{"value":True,"unit":"ppm"},{"value":1e10,"unit":"ppm"}])
    if k==7: p.pop(r.choice(list(p)))
    if k==8: p["extra"]=1
    if k==9: p=r.choice([5,None,[],"x"])
    return p
TERMS=None
def term():
    global TERMS
    if TERMS is None:
        t=json.load(open(ROOT / "foundations/refrigeration/foundation_refrigeration/data/plant-taxonomy.json"))["data"]
        TERMS=(list(t["aliases"])+[k["id"] for k in t["kinds"]], [x["code"] for x in t["line_services"]], [v for e in t["legacy_lists"] for v in e["values"]])
    k=r.random()
    if k<.5:
        s=r.choice(TERMS[0]+TERMS[2])
        m=r.randint(0,6)
        if m==1: s=s.upper()
        if m==2: s=s.replace("-"," ")
        if m==3: s=s.replace("-","_")
        if m==4: s=" "+s+"\t"
        if m==5: s=s.replace("-"," _ ")
        return s
    if k<.8:
        s=r.choice(TERMS[1]); return r.choice([s,s.lower()," "+s,s+"\n"])
    return r.choice(["","  ","?",5,None,True,[],"x"*128,"x"*129,"x"*16,"x"*17,"a\x1cb","\x1c","a--b","__proto__","constructor","toString","hasOwnProperty","a/b","\x7f"])
def gen():
    t=r.choice(["saturation_pressure"]*3+["saturation_temperature"]*3+["check_reading_against_saturation"]*3+["convert_pressure"]*2+["convert_temperature"]*2+["exposure_limits","resolve_equipment_kind"])
    if t=="saturation_pressure": a=opt({"fluid":r.choice(FL),"temperature":tq()},side=side(),atmosphere=atm())
    elif t=="saturation_temperature": a=opt({"fluid":r.choice(FL),"pressure":pq()},side=side(),atmosphere=atm())
    elif t=="check_reading_against_saturation": a=opt({"fluid":r.choice(FL),"pressure":pq(),"temperature":tq()},atmosphere=atm())
    elif t=="convert_pressure": a=opt({"pressure":pq(),"to_unit":r.choice(PU+["atm",5,None])},atmosphere=atm())
    elif t=="convert_temperature": a={"temperature":tq(),"to_unit":r.choice(TU+["R",5,None])}
    elif t=="exposure_limits":
        a=opt({"substance":r.choice(["ammonia"," NH3 ","R-717","r717","NH3\t","\x1cnh3","propane",5,None,"Ammonia","R717"])},issuer=r.choice([None,"OSHA","NIOSH","ACGIH","AIHA",5,False,[]]))
        if r.random()<.7: a["policy_set_points"]=r.choice([[pol() for _ in range(r.randint(0,3))],[POINT]*17,[POINT]*16,"x",None,{}])
    else:
        a=opt({"term":term()},vocabulary=r.choice([None,"equipment_kind","line_service","line_service","other",5]))
        if r.random()<.05: a["vocabulary"]=None
    return t,fuzz_extra(a)


def fuzz(n, seed):
    r.seed(seed)
    return [(tool, json.dumps(arguments, separators=(",", ":"))) for tool, arguments in (gen() for _ in range(n))]
