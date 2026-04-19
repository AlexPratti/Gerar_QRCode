import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd
import re

# Conexão
url = st.secrets["URL_SUPABASE"]
key = st.secrets["KEY_SUPABASE"]
supabase = create_client(url, key)

def process_docx(file):
    doc = Document(file)
    paragraphs = []
    for p in doc.paragraphs:
        t = p.text.strip()
        if t: paragraphs.append(t)
    
    data = []
    hinos_mapeados = []
    current_cat = "GERAL"
    
    # 1. VARREDURA DO SUMÁRIO (Identifica o que salvar)
    for text in paragraphs:
        # Se tem pontos guia, é sumário
        if "...." in text:
            # Remove os pontos e o número da página no final
            clean_text = re.sub(r'\.+\s*\d+$', '', text).strip()
            
            # Nível 1: CAIXA ALTA e não começa com número
            if clean_text.isupper() and not clean_text[0:1].isdigit():
                current_cat = clean_text
            # Nível 2: Começa com número
            elif clean_text[0:1].isdigit():
                hinos_mapeados.append({"cat": current_cat, "titulo": clean_text})
        
        # Para de ler o sumário ao chegar no conteúdo real
        if text == "ORANTES" and "...." not in text:
            break

    # 2. CAPTURA DO CONTEÚDO (Busca os títulos no corpo)
    conteudos = {h['titulo']: [] for h in hinos_mapeados}
    hino_foco = None

    for text in paragraphs:
        if text in conteudos:
            hino_foco = text
        elif hino_foco:
            # Se encontrar nova categoria ou outro hino, para
            if text in conteudos or (text.isupper() and len(text) < 50 and not text[0:1].isdigit()):
                hino_foco = None
            else:
                conteudos[hino_foco].append(text)
    
    for h in hinos_mapeados:
        data.append({
            "n1": h['cat'],
            "n2": h['titulo'],
            "texto": "\n".join(conteudos[h['titulo']])
        })
    return data

def save_to_db(data):
    # Limpeza total
    supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
    supabase.table("hinos_categorias").delete().neq("id", 0).execute()
    
    seen_cats = {}
    for item in data:
        cat_name = item['n1']
        if cat_name not in seen_cats:
            res = supabase.table("hinos_categorias").insert({"nome_nivel1": cat_name}).execute()
            # Ajuste de acesso ao ID retornado
            if hasattr(res, 'data') and len(res.data) > 0:
                seen_cats[cat_name] = res.data[0]['id']
        
        if cat_name in seen_cats:
            supabase.table("hinos_conteudos").insert({
                "categoria_id": seen_cats[cat_name],
                "nome_nivel2": item['n2'],
                "texto_completo": item['texto']
            }).execute()

# --- INTERFACE ---
st.set_page_config(page_title="Hinário", layout="wide")

with st.sidebar:
    st.title("⚙️ Admin")
    arquivo = st.file_uploader("Upload .docx", type="docx")
    if st.button("🚀 Processar Hinário"):
        if arquivo:
            with st.spinner("Gravando no banco..."):
                dados = process_docx(arquivo)
                if dados:
                    save_to_db(dados)
                    st.success(f"{len(dados)} hinos salvos!")
                    st.rerun()
                else:
                    st.error("Sumário não identificado.")

# --- EXIBIÇÃO ---
try:
    res_cat = supabase.table("hinos_categorias").select("*").order("id").execute()
    if res_cat.data:
        df_cat = pd.DataFrame(res_cat.data)
        c1, c2 = st.columns([1, 2])
        
        with c1:
            sel_n1 = st.selectbox("📌 Categoria:", df_cat['nome_nivel1'])
            cat_id = df_cat[df_cat['nome_nivel1'] == sel_n1]['id'].values[0]
            
            busca = st.text_input("🔍 Busca:")
            h_res = supabase.table("hinos_conteudos").select("*").eq("categoria_id", cat_id).order("id").execute().data
            
            if h_res:
                if busca:
                    h_res = [h for h in h_res if busca.lower() in h['nome_nivel2'].lower()]
                
                nomes = [h['nome_nivel2'] for h in h_res]
                if nomes:
                    escolha = st.radio("📑 Escolha:", nomes)
                    hino = next(h for h in h_res if h['nome_nivel2'] == escolha)
                    with c2:
                        st.subheader(hino['nome_nivel2'])
                        st.divider()
                        st.text(hino['texto_completo'])
    else:
        st.info("💡 Banco vazio. Suba o arquivo no menu lateral.")
except Exception as e:
    st.error(f"Aguardando dados: {e}")
