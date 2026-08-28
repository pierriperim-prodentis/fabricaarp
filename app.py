import json
import unicodedata
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------
st.set_page_config(page_title="Fábrica 2026 — Vendas", page_icon="🏭", layout="wide")

VIEW_KEY = "prodentis2026"

MONTH_LABELS = [
    "JANEIRO 2026", "FEVEREIRO 2026", "MARÇO 2026", "ABRIL 2026", "MAIO 2026",
    "JUNHO 2026", "JULHO 2026", "AGOSTO 2026", "SETEMBRO 2026", "OUTUBRO 2026",
    "NOVEMBRO 2026", "DEZEMBRO 2026",
]
MONTH_SHORT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

ASSESSOR_LOJA = {
    "bruna": "PMW", "made": "PMW", "luana": "PMW",
    "diego": "SLZ", "francely": "SLZ", "lizia": "SLZ",
    "jarlene": "ITZ",
}

DATA_PATH = Path(__file__).parent / "fabrica_data.json"


def norm(s: str) -> str:
    s = str(s or "")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower().strip()


def title_case(s: str) -> str:
    return " ".join(w.capitalize() for w in s.split())


JSONBIN_BIN_ID = "6a91c5cff5f4af5e294ebcf0"
JSONBIN_MASTER_KEY = "$2a$10$kDShjgaHn/S8k124l8ehU.lw9To/Dt0VHer/KXhF6XMT2CvljlxKm"


@st.cache_data(ttl=60)
def load_data():
    import requests
    try:
        res = requests.get(
            f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}/latest",
            headers={"X-Master-Key": JSONBIN_MASTER_KEY},
            timeout=10,
        )
        res.raise_for_status()
        return res.json()["record"]
    except Exception:
        with open(DATA_PATH, encoding="utf-8") as f:
            return json.load(f)


def fmt_money(v: float) -> str:
    s = f"{v:,.2f}"
    s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    return f"R$ {s}"


# ------------------------------------------------------------------
# Access gate
# ------------------------------------------------------------------
params = st.query_params
chave = params.get("chave", "")

if chave != VIEW_KEY:
    st.markdown(
        """
        <div style="text-align:center; padding: 120px 20px;">
            <h1 style="font-size:26px;">🔒 Acesso restrito</h1>
            <p style="color:#666;">Este painel exige uma chave de acesso válida na URL.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

DATA = load_data()

# ------------------------------------------------------------------
# Aggregate
# ------------------------------------------------------------------
month_totals = []
store_totals = {"PMW": 0.0, "SLZ": 0.0, "ITZ": 0.0}
grand_total = 0.0

for label in MONTH_LABELS:
    entry = DATA.get(label, {})
    totals = entry.get("totals_by_assessora", {})
    m_total = sum(v.get("total", v.get("faturadas", 0) + v.get("digitais", 0)) for v in totals.values())
    month_totals.append(m_total)
    for a, v in totals.items():
        loja = ASSESSOR_LOJA.get(a)
        subtotal = v.get("total", v.get("faturadas", 0) + v.get("digitais", 0))
        if loja:
            store_totals[loja] += subtotal
        grand_total += subtotal

# ------------------------------------------------------------------
# Header
# ------------------------------------------------------------------
st.markdown(
    "<div style='font-family:monospace; letter-spacing:.1em; color:#c9922b; "
    "font-size:12px; text-transform:uppercase;'>Pródentis / ARP — Fábrica 2026</div>",
    unsafe_allow_html=True,
)
st.title("Painel de Vendas de Fábrica")
st.caption("Dados extraídos da planilha \"Fábrica 2026 - Geral\" (última atualização enviada manualmente).")

# ------------------------------------------------------------------
# Cards
# ------------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total no ano", fmt_money(grand_total))
c2.metric("PMW · Palmas", fmt_money(store_totals["PMW"]))
c3.metric("SLZ · São Luís", fmt_money(store_totals["SLZ"]))
c4.metric("ITZ · Imperatriz", fmt_money(store_totals["ITZ"]))

st.divider()

# ------------------------------------------------------------------
# Month chart
# ------------------------------------------------------------------
st.subheader("Total por mês")
chart_df = pd.DataFrame({"Mês": MONTH_SHORT, "Total": month_totals})
chart = (
    alt.Chart(chart_df)
    .mark_bar(color="#1B2A4A")
    .encode(
        x=alt.X("Mês:N", sort=MONTH_SHORT, title=None),
        y=alt.Y("Total:Q", title=None),
        tooltip=[alt.Tooltip("Mês:N"), alt.Tooltip("Total:Q", format=",.2f")],
    )
    .properties(height=320)
)
st.altair_chart(chart, use_container_width=True)

st.divider()

# ------------------------------------------------------------------
# Month detail
# ------------------------------------------------------------------
st.subheader("Detalhe por assessora")
months_with_data = [MONTH_LABELS[i] for i, t in enumerate(month_totals) if t > 0] or [MONTH_LABELS[0]]
sel_label = st.selectbox("Mês", months_with_data, index=len(months_with_data) - 1)

entry = DATA.get(sel_label, {})
totals = entry.get("totals_by_assessora", {})
rows = []
for a, v in sorted(totals.items(), key=lambda kv: -kv[1].get("total", kv[1].get("faturadas", 0) + kv[1].get("digitais", 0))):
    fat = v.get("faturadas", 0)
    dig = v.get("digitais", 0)
    tot = v.get("total", fat + dig)
    rows.append({
        "Assessora": title_case(a),
        "Loja": ASSESSOR_LOJA.get(a, "—"),
        "Faturadas": fmt_money(fat),
        "Digitais": fmt_money(dig),
        "Total": fmt_money(tot),
    })
detail_df = pd.DataFrame(rows)
st.dataframe(detail_df, use_container_width=True, hide_index=True)
total_fat = sum(v.get("faturadas", 0) for v in totals.values())
total_dig = sum(v.get("digitais", 0) for v in totals.values())
total_geral = sum(v.get("total", v.get("faturadas", 0) + v.get("digitais", 0)) for v in totals.values())
st.markdown(
    f"**Total do mês:** {fmt_money(total_geral)}  ·  "
    f"Faturadas: {fmt_money(total_fat)}  ·  Digitais: {fmt_money(total_dig)}"
)

# ------------------------------------------------------------------
# Line-item detail
# ------------------------------------------------------------------
st.divider()
st.subheader("Detalhamento linha a linha")
details = entry.get("details", [])
if details:
    det_df = pd.DataFrame(details)
    det_df = det_df.rename(columns={
        "assessora": "Assessora", "cliente": "Cliente", "data": "Data",
        "valor": "Valor", "instituicao": "Instituição", "tipo": "Tipo",
    })
    det_df["Tipo"] = det_df["Tipo"].map({"faturada": "Faturada", "digital": "Digital"}).fillna(det_df["Tipo"])
    det_df["Valor"] = det_df["Valor"].apply(fmt_money)
    det_df = det_df[["Tipo", "Assessora", "Cliente", "Data", "Instituição", "Valor"]]
    st.dataframe(det_df, use_container_width=True, hide_index=True)
else:
    st.info("Sem lançamentos detalhados para este mês.")

st.caption(
    "Para atualizar os dados: reenvie a planilha (ou exporte as abas em .xlsx) "
    "para regenerar o arquivo fabrica_data.json e faça o commit no repositório."
)
