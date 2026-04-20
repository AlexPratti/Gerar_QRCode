import streamlit as st
import pdfplumber
import re
from supabase import create_client
import pandas as pd
import io

# Conexão original
supabase = create_client(st.secrets["URL_SUPABASE"], st.secrets["KEY_SUPABASE"])
BUCKET = "hinarios"

# Lista fixa para o Hinário Litúrgico
CATEGORIAS_LITURGICOS = ["ORANTES", "INICIAIS E FINAIS", "PERDÃO", "GLÓRIA", "DEUS NOS FALA", "SALMO", "ACLAMAÇÃO", "OFERTÓRIO", "LOUVOR", "SANTO", "CORDEIRO", "PAZ", "COMUNHÃO", "BÍBLIA", "CRUZ", "LADAINHAS – SEQUÊNCIAS - PROCLAMAÇÕES", "MARIA", "PRECES"]

def process_pdf(file, categoria_fixa=None):
    data = []
    current_n1 = categoria_fixa if categoria_fixa else "Sem Categoria"
    
    with pdfplumber.open(file) as pdf:
        progresso = st.progress(0)
        total_pags = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            text = page.extract_text(layout=True)
            if not text: continue
            
            for line in text.split('\n'):
                t_limpo = line.strip()
                if not t_limpo or "...." in t_limpo: continue

                # Se não houver categoria fixa, busca na lista (Caso do Litúrgico)
                if not categoria_fixa and t_limpo.upper() in CATEGORIAS_LITURGICOS:
                    current_n1 = t_limpo.upper()
                    continue

                # Identifica Hino (Número + Ponto)
                if re.match(r'^\d+\.', t_limpo):
                    data.append({"n1": current_n1, "n2": t_limpo, "pag": i + 1})
            
            progresso.progress((i + 1) / total_pags)
    return data

def save_to_db(data):
    # Limpa apenas para o novo processamento
    supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
    supabase.table("hinos_categorias").delete().neq("id", 0).execute()
    
    categorias_presentes = sorted(list(set([item['n1'] for item in data])))
    for cat_nome in categorias_presentes:
        res = supabase.table("hinos_categorias").insert({"nome_nivel1": cat_nome}).execute()
        if res.data:
            # Pega o ID (Garante compatibilidade com retorno do Supabase)
            cat_id = res.data['id'] if isinstance(res.data, list) else res.data['id']
            itens = [{"categoria_id": cat_id, "nome_nivel2": item['n2'], "texto_completo": str(item['pag'])} for item in data if item['n1'] == cat_nome]
            if itens:
                supabase.table("hinos_conteudos").insert(itens).execute()
st.set_page_config(page_title="Hinário", layout="wide")
tab1, tab2 = st.tabs(["📖 HINOS LITÚRGICOS", "🎸 HINOS DIVERSOS"])

# --- ABA 1: HINOS LITÚRGICOS ---
with tab1:
    NOME_STORAGE_LIT = "hinos_liturgicos.pdf"
    try:
        res_lit = supabase.storage.from_(BUCKET).download(NOME_STORAGE_LIT)
        pdf_lit = io.BytesIO(res_lit)
    except: pdf_lit = None

    with st.expander("⬆️ Atualizar Hinos Litúrgicos"):
        up_lit = st.file_uploader("Upload PDF Litúrgico", type="pdf", key="up1")
        if st.button("Sincronizar Litúrgicos"):
            bytes_lit = up_lit.read()
            try: supabase.storage.from_(BUCKET).remove([NOME_STORAGE_LIT])
            except: pass
            supabase.storage.from_(BUCKET).upload(path=NOME_STORAGE_LIT, file=bytes_lit)
            dados = process_pdf(io.BytesIO(bytes_lit)) # Busca categorias na lista
            save_to_db(dados)
            st.rerun()

    # Exibição (Mesma lógica de crop)
    if pdf_lit:
        # Nota: O banco sempre reflete o último arquivo sincronizado
        res_cat = supabase.table("hinos_categorias").select("*").order("nome_nivel1").execute()
        if res_cat.data:
            df = pd.DataFrame(res_cat.data)
            c1, c2 = st.columns(2)
            with c1:
                sel_cat = st.selectbox("Categoria", df['nome_nivel1'], key="c_lit")
                id_cat = int(df[df['nome_nivel1'] == sel_cat]['id'].iloc[0])
            hinos = supabase.table("hinos_conteudos").select("*").eq("categoria_id", id_cat).execute().data
            if hinos:
                hinos_ord = sorted(hinos, key=lambda x: int(re.search(r'\d+', x['nome_nivel2']).group()))
                hino_sel = st.selectbox("Hino", [h['nome_nivel2'] for h in hinos_ord], key="h_lit")
                item = next(h for h in hinos if h['nome_nivel2'] == hino_sel)
                p_num = int(item['texto_completo'])
                with pdfplumber.open(pdf_lit) as pdf:
                    page = pdf.pages[p_num - 1]
                    lines = page.extract_text_lines()
                    y_ini = next((l['top'] for l in lines if hino_sel in l['text']), 0)
                    y_fim = page.height
                    for l in lines:
                        if l['top'] > y_ini + 5:
                            if re.match(r'^\d+\.', l['text'].strip()) or l['text'].strip().upper() in CATEGORIAS_LITURGICOS:
                                y_fim = l['top']; break
                    st.image(page.crop((0, max(0, y_ini-10), page.width, y_fim)).to_image(resolution=200).original, use_container_width=True)

# --- ABA 2: HINOS DIVERSOS ---
with tab2:
    NOME_STORAGE_DIV = "hinos_diversos.pdf"
    try:
        res_div = supabase.storage.from_(BUCKET).download(NOME_STORAGE_DIV)
        pdf_div = io.BytesIO(res_div)
    except: pdf_div = None

    with st.expander("⬆️ Atualizar Hinos Diversos"):
        up_div = st.file_uploader("Upload PDF Diversos", type="pdf", key="up2")
        if st.button("Sincronizar Diversos"):
            bytes_div = up_div.read()
            try: supabase.storage.from_(BUCKET).remove([NOME_STORAGE_DIV])
            except: pass
            supabase.storage.from_(BUCKET).upload(path=NOME_STORAGE_DIV, file=bytes_div)
            dados = process_pdf(io.BytesIO(bytes_div), categoria_fixa="HINOS DIVERSOS") # Força categoria
            save_to_db(dados)
            st.rerun()

    if pdf_div:
        # (Repete a lógica de exibição para o PDF Diversos)
        res_cat = supabase.table("hinos_categorias").select("*").eq("nome_nivel1", "HINOS DIVERSOS").execute()
        if res_cat.data:
            id_cat = res_cat.data[0]['id']
            hinos = supabase.table("hinos_conteudos").select("*").eq("categoria_id", id_cat).execute().data
            if hinos:
                hinos_ord = sorted(hinos, key=lambda x: int(re.search(r'\d+', x['nome_nivel2']).group()))
                hino_sel = st.selectbox("Hino", [h['nome_nivel2'] for h in hinos_ord], key="h_div")
                item = next(h for h in hinos if h['nome_nivel2'] == hino_sel)
                p_num = int(item['texto_completo'])
                with pdfplumber.open(pdf_div) as pdf:
                    page = pdf.pages[p_num - 1]
                    lines = page.extract_text_lines()
                    y_ini = next((l['top'] for l in lines if hino_sel in l['text']), 0)
                    y_fim = page.height
                    for l in lines:
                        if l['top'] > y_ini + 5 and re.match(r'^\d+\.', l['text'].strip()):
                            y_fim = l['top']; break
                    st.image(page.crop((0, max(0, y_ini-10), page.width, y_fim)).to_image(resolution=200).original, use_container_width=True)
