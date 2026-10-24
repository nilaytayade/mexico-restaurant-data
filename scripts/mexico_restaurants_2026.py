"""Mexico's restaurant industry in numbers, from INEGI's DENUE (edition 05/2026).

Reproduces every figure in /insights/mexico-restaurant-industry-data-2026:
the CSVs under public/data/mexico-restaurants-2026/ and the charts under
content/insights/mexico-restaurant-industry-data-2026/charts/.

  python3 scripts/data/mexico_restaurants_2026.py <dir with denue_inegi_72_*.csv>

Source: INEGI, Directorio Estadístico Nacional de Unidades Económicas (DENUE),
05/2026, sector 72, downloaded from inegi.org.mx/app/descarga (bulk CSV,
denue_00_72_1_csv.zip and denue_00_72_2_csv.zip). Scope: SCIAN 7225
(restaurants, cafés and other places that prepare food and drink to eat
now); bars (7224), catering (7223) and lodging (721) are left out.

Groups: DENUE lists the legal name (razón social) for about one in eight
establishments, mostly the larger ones, and many of those are a person's
name. An establishment counts toward a group only when its legal name
reads as a company (Operadora, Grupo, Restaurantes, Corporativo, Alimentos
and similar) and the same name appears at two or more establishments. That
is a floor, not a census: groups that use one company per branch,
franchisees and small groups without a recorded legal name don't show up.
"""

import glob, json, os, re, sys, unicodedata

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
from matplotlib import font_manager
import pandas as pd

SRC = sys.argv[1]
ROOT = os.environ.get("CODEX_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "public", "data", "mexico-restaurants-2026")
CHARTS = os.path.join(ROOT, "content", "insights", "mexico-restaurant-industry-data-2026", "charts")
os.makedirs(DATA, exist_ok=True)
os.makedirs(CHARTS, exist_ok=True)

cols = ["id", "raz_social", "codigo_act", "nombre_act", "per_ocu", "cve_ent", "entidad", "municipio"]
df = pd.concat(pd.read_csv(f, encoding="latin1", dtype=str, usecols=cols) for f in glob.glob(os.path.join(SRC, "**", "denue_inegi_72_*.csv"), recursive=True))
r = df[df["codigo_act"].str.startswith("7225")].copy()
bars = int(df["codigo_act"].str.startswith("7224").sum())

BANDS = ["0 a 5 personas", "6 a 10 personas", "11 a 30 personas", "31 a 50 personas", "51 a 100 personas", "101 a 250 personas", "251 y más personas"]
BAND_SHORT = {b: s for b, s in zip(BANDS, ["0-5", "6-10", "11-30", "31-50", "51-100", "101-250", "251+"])}
r["staff"] = r["per_ocu"].map(BAND_SHORT)
r["eleven_plus"] = ~r["per_ocu"].isin(BANDS[:2])

TYPE_EN = {
    "722511": "Full-service, à la carte or set menu", "722512": "Seafood", "722513": "Antojitos",
    "722514": "Tacos and tortas", "722515": "Cafés, ice cream, juice and soda fountains", "722516": "Self-service",
    "722517": "Pizza, burgers, hot dogs, rotisserie chicken (takeout)", "722518": "Other takeout",
    "722519": "Other food for immediate consumption",
}
r["type_es"] = r["nombre_act"]
r["type_en"] = r["codigo_act"].map(TYPE_EN)

# ── establishments ──────────────────────────────────────────────────────────
total = len(r)
by_band = r["staff"].value_counts().reindex(BAND_SHORT.values()).fillna(0).astype(int)
by_state = r.groupby("entidad").agg(establishments=("id", "size"), eleven_plus=("eleven_plus", "sum")).reset_index()
by_state["eleven_plus_share_pct"] = (by_state["eleven_plus"] / by_state["establishments"] * 100).round(1)
by_state = by_state.sort_values("establishments", ascending=False)
by_state.to_csv(os.path.join(DATA, "by_state.csv"), index=False)

by_type = r.groupby(["codigo_act", "type_es", "type_en"]).agg(establishments=("id", "size"), eleven_plus=("eleven_plus", "sum")).reset_index()
by_type["eleven_plus_share_pct"] = (by_type["eleven_plus"] / by_type["establishments"] * 100).round(1)
by_type = by_type.sort_values("establishments", ascending=False)
by_type.to_csv(os.path.join(DATA, "by_type.csv"), index=False)

r.groupby(["entidad", "codigo_act", "staff"]).size().rename("establishments").reset_index().to_csv(os.path.join(DATA, "by_state_type_staff.csv"), index=False)

mun = r[r["eleven_plus"]].groupby(["entidad", "municipio"]).size().rename("eleven_plus").reset_index().sort_values("eleven_plus", ascending=False)
mun.to_csv(os.path.join(DATA, "eleven_plus_by_municipality.csv"), index=False)

# ── groups (company-named legal entities at 2+ establishments) ─────────────
def norm(s):
    if not isinstance(s, str):
        return None
    s = unicodedata.normalize("NFKD", s.upper())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[.,]", " ", s)
    s = re.sub(r"\b(S ?A ?P ?I|S ?A ?B|S ?A|S ?DE ?R ?L|S ?R ?L|DE C ?V|C ?V|S ?C|S ?A ?S|SOCIEDAD ANONIMA|PROMOTORA DE INVERSION|CAPITAL VARIABLE|DE|R ?L)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip() or None

COMPANY = re.compile(r"\b(OPERADORA|GRUPO|RESTAURANT\w*|CORPORATIV\w*|SERVICIOS|ALIMENT\w*|GASTRONOM\w*|HOLDING\w*|FOODS?|COMERCIALIZADORA|PROMOTORA|INMOBILIARIA|ADMINISTRADORA|DESARROLL\w*|INVERSION\w*|CONCEPTOS|FRANQUICI\w*|EMPRESAS|INDUSTRIAS|ENTERPRISES|BRANDS|HOSPITALITY|IMPULSORA|COMPANIA|CIA|PROVEEDORA|DISTRIBUIDORA|CADENA|SUPER|INTERNACIONAL|MEXICANA|CONSORCIO|MARCAS|INVERSIONES)\b")
r["entity"] = r["raz_social"].map(norm)
co = r[r["entity"].notna() & r["entity"].str.contains(COMPANY)]
sizes = co.groupby("entity").size()
def band(n):
    return "1" if n == 1 else "2-5" if n <= 5 else "6-15" if n <= 15 else "16-50" if n <= 50 else "51+"
group_bands = sizes.map(band).value_counts().reindex(["2-5", "6-15", "16-50", "51+"]).fillna(0).astype(int)
multi = sizes[sizes >= 2]
mco = co[co["entity"].isin(multi.index)]
home = mco.groupby("entity")["entidad"].agg(lambda x: x.value_counts().index[0])
states_per = mco.groupby("entity")["entidad"].nunique()
gstate = pd.DataFrame({"home_state": home, "size": multi, "states": states_per})
gstate["band"] = gstate["size"].map(band)
groups_by_state = gstate.pivot_table(index="home_state", columns="band", values="size", aggfunc="count", fill_value=0)
groups_by_state = groups_by_state.reindex(columns=["2-5", "6-15", "16-50", "51+"], fill_value=0)
groups_by_state["total"] = groups_by_state.sum(axis=1)
groups_by_state.sort_values("total", ascending=False).to_csv(os.path.join(DATA, "groups_by_home_state.csv"))
small = gstate[(gstate["size"] >= 2) & (gstate["size"] <= 15)]

summary = {
    "source": "INEGI, DENUE 05/2026 (modified 2026-05-20), sector 72, SCIAN 7225",
    "restaurant_establishments": total,
    "bars_7224_not_included": bars,
    "staff_bands": by_band.to_dict(),
    "staff_0_5_share_pct": round(by_band["0-5"] / total * 100, 1),
    "eleven_plus": int(r["eleven_plus"].sum()),
    "eleven_plus_share_pct": round(r["eleven_plus"].mean() * 100, 1),
    "groups_min": {"2-5": int(group_bands["2-5"]), "6-15": int(group_bands["6-15"]), "16-50": int(group_bands["16-50"]), "51+": int(group_bands["51+"])},
    "groups_2_15_total": int(len(small)),
    "groups_2_15_establishments": int(small["size"].sum()),
    "groups_2_15_single_state_share_pct": round((small["states"] == 1).mean() * 100, 1),
    "groups_16_plus_total": int((sizes >= 16).sum()),
    "groups_16_plus_establishments": int(sizes[sizes >= 16].sum()),
    "staff_band_share_in_2_15_groups_pct": (mco[mco["entity"].isin(small.index)]["staff"].value_counts(normalize=True) * 100).round(1).reindex(BAND_SHORT.values()).fillna(0).to_dict(),
}
json.dump(summary, open(os.path.join(DATA, "summary.json"), "w"), ensure_ascii=False, indent=1)

# ── charts (state names and band labels read the same in both languages) ───
for f in glob.glob(os.path.join(ROOT, "assets", "fonts", "Outfit-*.ttf")):
    font_manager.fontManager.addfont(f)
plt.rcParams.update({"font.family": "Outfit", "font.size": 15})
CREAM, INK, FOREST, GOLD, MUTED = "#FBF8F1", "#10241A", "#1A472A", "#E6B33D", "#5C615C"

top = by_state.sort_values("eleven_plus", ascending=False).head(12).iloc[::-1]
fig, ax = plt.subplots(figsize=(12, 7.2), dpi=150)
fig.patch.set_facecolor(CREAM); ax.set_facecolor(CREAM)
names = top["entidad"].str.replace(" de Ignacio de la Llave", "").str.replace(" de Zaragoza", "").replace({"México": "Estado de México"})
b = ax.barh(names, top["eleven_plus"], color=FOREST, height=0.62)
for rect, n, sh in zip(b, top["eleven_plus"], top["eleven_plus_share_pct"]):
    ax.text(rect.get_width() + 40, rect.get_y() + rect.get_height() / 2, f"{int(n):,}  ·  {sh}%", va="center", color=INK, fontsize=14, fontweight="semibold")
ax.set_xlim(0, top["eleven_plus"].max() * 1.28)
for s in ["top", "right", "bottom"]: ax.spines[s].set_visible(False)
ax.spines["left"].set_color("#D9D3C4"); ax.tick_params(axis="x", bottom=False, labelbottom=False); ax.tick_params(axis="y", colors=INK, length=0)
fig.text(0.01, 0.02, "INEGI, DENUE 05/2026 · restaurantcodex.com", color=MUTED, fontsize=11)
plt.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(os.path.join(CHARTS, "eleven-plus-by-state.png"), facecolor=CREAM); plt.close(fig)

fig, ax = plt.subplots(figsize=(12, 6.2), dpi=150)
fig.patch.set_facecolor(CREAM); ax.set_facecolor(CREAM)
labels = list(BAND_SHORT.values()); vals = [by_band[l] for l in labels]
colors = [FOREST if i < 2 else GOLD for i in range(len(labels))]
b = ax.bar(labels, vals, color=colors, width=0.62)
for rect, v in zip(b, vals):
    pct = v / total * 100
    ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height() * 1.18, f"{v:,}\n{pct:.1f}%" if pct >= 0.1 else f"{v:,}\n<0.1%", ha="center", va="bottom", color=INK, fontsize=13, fontweight="semibold")
ax.set_yscale("log"); ax.set_ylim(10, max(vals) * 8)
ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
for s in ["top", "right", "left"]: ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color("#D9D3C4"); ax.tick_params(axis="y", left=False, labelleft=False); ax.tick_params(axis="x", colors=INK, length=0)
fig.text(0.01, 0.02, "INEGI, DENUE 05/2026 · restaurantcodex.com", color=MUTED, fontsize=11)
plt.tight_layout(rect=(0, 0.05, 1, 1)); fig.savefig(os.path.join(CHARTS, "staff-bands.png"), facecolor=CREAM); plt.close(fig)

print(json.dumps(summary, ensure_ascii=False, indent=1))
