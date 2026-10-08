from __future__ import annotations
import hashlib, os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

XLSX = Path(os.getenv("CHILLI_XLSX", r"C:\Users\diks2\Downloads\Chilli_Powder_Floor_Data_Collection.xlsx"))
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
RELNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
SHEETS = ["1_Output", "2_Stops", "3_Settings", "4_Changes", "5_Response"]
STAGES = ["Cleaning", "Grinding", "Packing"]
@dataclass
class WorkbookData:
    plans: dict
    rows: dict[str, list[dict]]
    source: str
    fingerprint: str = ""
    skipped_rows: list[dict] = field(default_factory=list)

def _excel_date(value):
    try: return (datetime(1899, 12, 30) + timedelta(days=float(value))).date().isoformat()
    except Exception: return value

def _cell_value(cell, shared):
    v = cell.find("m:v", NS); value = "" if v is None else (v.text or "")
    if cell.attrib.get("t") == "s" and value: value = shared[int(value)]
    return value

def load_workbook(path: Path = XLSX) -> WorkbookData:
    if not path.exists(): return WorkbookData({}, {s: [] for s in SHEETS}, "missing workbook")
    fingerprint = hashlib.sha256(path.read_bytes()).hexdigest(); skipped=[]
    with ZipFile(path) as z:
        shared=[]
        if "xl/sharedStrings.xml" in z.namelist():
            root=ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared=["".join(t.text or "" for t in si.iterfind(".//m:t", NS)) for si in root.findall("m:si", NS)]
        wb=ET.fromstring(z.read("xl/workbook.xml")); rels=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        relmap={r.attrib["Id"]:r.attrib["Target"] for r in rels}; sheets={}
        for sheet in wb.find("m:sheets", NS):
            name=sheet.attrib["name"]; target=relmap[sheet.attrib[f"{{{RELNS}}}id"]]; target=target if target.startswith("xl/") else "xl/"+target
            root=ET.fromstring(z.read(target)); rows=[]
            for row in root.findall(".//m:sheetData/m:row", NS):
                item={}
                for cell in row.findall("m:c", NS): item[cell.attrib.get("r", "").rstrip("0123456789")]=_cell_value(cell, shared)
                rows.append(item)
            sheets[name]=rows
    plans={}
    for row in sheets.get("Plan", [])[4:]:
        if row.get("A"):
            try: value=float(row.get("B", ""))
            except ValueError: value=row.get("B", "")
            plans[row["A"]]={"value":value,"unit":row.get("C","")}
    normalized={}
    for sheet in SHEETS:
        raw=sheets.get(sheet, []); headers=raw[0] if raw else {}; normalized[sheet]=[]
        for row in raw[1:]:
            record={headers.get(col,col):val for col,val in row.items()}
            # 1_Output!26 is a units legend, not an event.
            if not record.get("Stage") and (not record.get("Date") or (isinstance(record.get("Date"), str) and record.get("Date").count("-") != 2)):
                if any(str(v).strip() for v in record.values()): skipped.append({"sheet":sheet,"reason":"non-data note","values":record})
                continue
            if "Date" in record: record["Date"]=_excel_date(record["Date"])
            normalized[sheet].append(record)
    return WorkbookData(plans, normalized, str(path), fingerprint, skipped)

def _num(value):
    try: return float(str(value).replace(",", ""))
    except Exception: return None

def validate(data):
    errors=[]
    for sheet in SHEETS:
        for i,row in enumerate(data.rows.get(sheet,[]),2):
            if not row.get("Date"): errors.append({"sheet":sheet,"row":i,"field":"Date","issue":"missing"})
            if not row.get("Stage"): errors.append({"sheet":sheet,"row":i,"field":"Stage","issue":"missing"})
            elif row["Stage"] not in STAGES: errors.append({"sheet":sheet,"row":i,"field":"Stage","issue":"unknown"})
            for field in ("Good Count","Reject Count","Target","Minutes","Reading"):
                if field in row and row[field] not in (None,"") and _num(row[field]) is None: errors.append({"sheet":sheet,"row":i,"field":field,"issue":"must be numeric"})
    return errors

def metrics(data):
    result={}
    for stage in STAGES:
        outputs=[r for r in data.rows["1_Output"] if r.get("Stage")==stage]; settings=[r for r in data.rows["3_Settings"] if r.get("Stage")==stage]; stops=[r for r in data.rows["2_Stops"] if r.get("Stage")==stage]; changes=[r for r in data.rows["4_Changes"] if r.get("Stage")==stage]; responses=[r for r in data.rows["5_Response"] if r.get("Stage")==stage]
        good=sum(_num(r.get("Good Count")) or 0 for r in outputs); rejects=sum(_num(r.get("Reject Count")) or 0 for r in outputs); target=sum(_num(r.get("Target")) or 0 for r in outputs)
        out_spec=[r for r in settings if str(r.get("In Spec","")).upper() not in ("OK","YES","Y")]; missing=[r for r in settings if not r.get("Reading")]; no_std=[r for r in changes if str(r.get("Standard Checked","")).upper()=="N"]; failed=[r for r in responses if str(r.get("Worked?","")).lower()=="no"]
        result[stage]={"date":outputs[0].get("Date") if outputs else None,"good":good,"rejects":rejects,"target":target,"pct_target":good/target if target else 0,"stop_minutes":sum(_num(r.get("Minutes")) or 0 for r in stops),"out_of_spec":len(out_spec),"missing":len(missing),"changes":len(changes),"changes_without_standard":len(no_std),"failed_actions":len(failed),"settings_out":out_spec[:10],"stops":stops,"changes_rows":changes,"responses":responses}
    return result

def rca(stage,m,data):
    base={"stage":stage,"status":"WATCH","cause":"No confirmed cause","four_m":"Method","waste":[],"actions":[],"escalate_to":[],"confidence":0.35,"evidence":[],"quality_hold":False}
    settings=data.rows["3_Settings"]
    def has(param,predicate): return [r for r in settings if r.get("Stage")==stage and r.get("Parameter")==param and predicate(_num(r.get("Reading")))]
    if stage=="Cleaning" and (has("Foreign matter and stalks in raw sample",lambda x:x is not None and x>2) or has("Reject bin since last check",lambda x:x is not None and x>35)):
        base.update(status="HOLD",cause="Incoming raw chilli lot is carrying excess foreign matter/stalks",four_m="Material",quality_hold=True,actions=["Hold the affected raw lot","Sample and test foreign matter before release","Switch to the graded lot","Call QA, stores, and shift lead"],escalate_to=["Shift lead","QA","Stores"],confidence=.95)
    elif stage=="Grinding" and (has("Hammer set run hours",lambda x:x is not None and x>400) or has("Sieve pass at 40 mesh",lambda x:x is not None and x<95)):
        base.update(status="HOLD",cause="Hammer set was run past life and sieve performance deteriorated",four_m="Machine",quality_hold=True,actions=["Do not raise feed to catch up","Hold powder pending QA colour and mesh checks","Call maintenance for hammer replacement","Resume only below the powder temperature limit"],escalate_to=["Maintenance","QA"],confidence=.96)
    elif stage=="Packing" and has("Dust extraction suction at filler",lambda x:x is not None and x<250):
        base.update(status="HOLD",cause="Dust collector suction is below the minimum and is affecting seal integrity",four_m="Machine",quality_hold=True,actions=["Hold potentially leaking pouches","Call maintenance to restore dust collector air","Check all air lines after compressor work","Keep seal temperature on the setup sheet"],escalate_to=["Maintenance","QA"],confidence=.96)
    else: base.update(status="WATCH" if m["pct_target"]>=.9 else "ACTION",actions=["Check the next scheduled reading","Log any change and response"],confidence=.55)
    base["evidence"]=[{"kind":"metric","label":"% of target","value":round(m["pct_target"]*100,1)},{"kind":"metric","label":"out-of-spec readings","value":m["out_of_spec"]},{"kind":"metric","label":"stop minutes","value":m["stop_minutes"]}]
    return base


