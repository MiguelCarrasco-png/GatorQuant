# PROTOTYPE, throwaway. Question: which title should the design paper carry?
# Four title variants on the real paper page 1 (real preamble, real abstract), switchable
# in titles.html via ?variant= and a floating bar (arrow keys work too).
# Run: python latex/prototype-titles/build.py   then open latex/prototype-titles/titles.html
import base64, pathlib, re, subprocess

HERE = pathlib.Path(__file__).resolve().parent
LATEX = HERE.parent
SUB = r"\\ \large Design paper --- MultiPlanetary Exchange System, Gator Quant Hacks 2026"

VARIANTS = {
    "A": ("Current: concept + architecture",
          "Money on the Table: Home Ledgers for a MultiPlanetary Exchange"),
    "B": ("Guarantee-led: the promise first",
          "Lost Packets Cost Time, Never Money: A Pre-Funded Exchange Across the Solar System"),
    "C": ("Plain descriptive: what it is",
          "A Hub-Free, Fully Pre-Funded Exchange for Nine Settlements"),
    "D": ("Rule-led: the one rule behind everything",
          "Nothing Owed Across Light-Lag: Home Ledgers for a MultiPlanetary Exchange"),
}

paper = (LATEX / "paper.tex").read_text(encoding="utf-8")
out = HERE / "build"
out.mkdir(exist_ok=True)
pages = {}
for key, (label, title) in VARIANTS.items():
    tex = re.sub(r"\\title\{.*\}", lambda _: r"\title{" + title + " " + SUB + "}", paper, count=1)
    name = f"title-{key}"
    (LATEX / f"{name}.tex").write_text(tex, encoding="utf-8")
    try:
        subprocess.run(["pdflatex", "-interaction=nonstopmode", f"-output-directory={out}", f"{name}.tex"],
                       cwd=LATEX, capture_output=True)
    finally:
        (LATEX / f"{name}.tex").unlink()
    log = (out / f"{name}.log").read_text(errors="ignore").replace("\n", "")
    m = re.search(r"Output written on .*?\((\d+) page", log)
    pages[key] = m.group(1) if m else "?"
    subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-r", "110", "-png", "-singlefile",
                    str(out / f"{name}.pdf"), str(out / name)], check=True)

imgs = {k: base64.b64encode((out / f"title-{k}.png").read_bytes()).decode() for k in VARIANTS}
data = ",".join(f'{k}:{{label:{VARIANTS[k][0]!r},title:{VARIANTS[k][1]!r},pages:{pages[k]!r},img:"{imgs[k]}"}}'
                for k in VARIANTS)
html = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Title Prototype</title><style>
body{margin:0;background:#e8e8e8;font:14px system-ui,sans-serif}
.note{max-width:860px;margin:12px auto;color:#333}
img{display:block;max-width:860px;width:calc(100% - 32px);margin:0 auto 90px;box-shadow:0 2px 12px #0003;background:#fff}
.bar{position:fixed;bottom:18px;left:50%;transform:translateX(-50%);display:flex;gap:10px;align-items:center;
background:#111;color:#fff;padding:8px 14px;border-radius:999px;box-shadow:0 4px 16px #0005;white-space:nowrap}
.bar button{background:#333;color:#fff;border:0;border-radius:50%;width:30px;height:30px;font-size:16px;cursor:pointer}
</style></head><body>
<div class="note">PROTOTYPE: paper page 1 with each candidate title. Same preamble and abstract; only the title differs.
Full paper length with this title: <b id="pg"></b> pages (limit 12).</div>
<img id="im" alt="paper page 1">
<div class="bar"><button id="prev">&larr;</button><span id="lab"></span><button id="next">&rarr;</button></div>
<script>
const V={""" + data + """};const K=Object.keys(V);
let cur=new URLSearchParams(location.search).get('variant');if(!V[cur])cur='A';
function show(k){cur=k;const v=V[k];im.src='data:image/png;base64,'+v.img;lab.textContent=k+' ('+v.label+')';
pg.textContent=v.pages;try{history.replaceState(null,'','?variant='+k)}catch(e){}}
function step(d){show(K[(K.indexOf(cur)+d+K.length)%K.length])}
prev.onclick=()=>step(-1);next.onclick=()=>step(1);
addEventListener('keydown',e=>{if(e.key==='ArrowLeft')step(-1);if(e.key==='ArrowRight')step(1)});show(cur);
</script></body></html>"""
(HERE / "titles.html").write_text(html, encoding="utf-8")
print("pages per variant:", pages)
