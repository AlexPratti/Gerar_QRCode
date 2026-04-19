import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd
import re

# Conexão segura com Supabase
supabase = create_client(st.secrets["URL_SUPABASE"], st.secrets["KEY_SUPABASE"])

def process_docx(file):
    doc = Document(file)
    paragraphs = []
    # Captura parágrafos de forma simples para evitar erro de sintaxe
    for p in doc.paragraphs:
        txt = p.text.strip()
        if txt:
            paragraphs.append(txt)
    
    data = []
    hinos_mapeados = []
    current_cat = "GERAL"
    
    # 1. VARREDURA DO SUMÁRIO (Baseado no seu PDF)
    for text in paragraphs:
        # Identifica linhas do sumário pelos pontinhos guia
        if "...." in text:
            # Limpa o texto: remove os pontos e o número da página no fim
            clean_text = re.sub(r'\.+\s*\d+$', '', text).strip()
            
            # REGRA NÍVEL 1: Tudo em CAIXA ALTA e não começa com número
            if clean_text.isupper() and not clean_text[0:1].isdigit():
                current_cat = clean_text
            
            # REGRA NÍVEL 2: Começa com número
            elif clean_text[0:1].isdigit():
                hinos_mapeados.append({"cat": current_cat, "titulo": clean_text})
        
        # Para de ler o sumário quando encontra o conteúdo real (página 10)
        if text == "ORANTES" and "...." not in text:
            break

    # 2. CAPTURA DO CONTEÚDO (Corpo do Texto)
    # Criamos um mapa para armazenar as letras de cada título achado no sumário
    conteudos = {}
    for h in hinos_mapeados:
        conteudos[h['titulo']] = []
        
    hino_foco = None

    for text in paragraphs:
        # Se a linha for exatamente um dos títulos do sumário, muda o foco
        if text in conteudos:
            hino_foco = text
        elif hino_foco:
            # Se não for outro título, é a letra do hino atual
            if text not in conteudos:
                conteudos[hino_foco].append(text)
    
    # 3. MONTAGEM DO DICIONÁRIO FINAL
    for h in hinos_mapeados:
        data.append({
            "n1": h['cat'],
            "n2": h['titulo'],
            "texto": "\n".join(conteudos[h['titulo']])
        })
    return data

def save_to_db(data):
    # Limpa dados para sobreposição
    supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
    supabase.table("hinos_categorias").delete().neq("id", 0).execute()
    
    seen_cats = {}
    for item in data:
        cat_name = item['n1']
        if cat_name not in seen_cats:
            res = supabase.table("hinos_categorias").insert({"nome_nivel1": cat_name}).execute()
            if res.data:
                # No Supabase Python, res.data é uma lista. Pegamos o ID do primeiro item.
                seen_cats[cat_name] = res.data[0]['id']
        
        if cat_name in seen_cats:
            supabase.table("hinos_conteudos").insert({
                "categoria_id": seen_cats[cat_name],
                "nome_nivel2": item['n2'],
                "texto_completo": item['texto']
            }).execute()

# --- INTERFACE ---
st.set_page_config(page_title="Hinário Litúrgico", layout="wide")

with st.sidebar:
    st.title("⚙️ Painel Admin")
    arquivo = st.file_uploader("Suba o arquivo .docx", type="docx")
    if st.button("🚀 Processar Hinário"):
        if arquivo:
            with st.spinner("Lendo sumário e hinos..."):
                dados = process_docx(arquivo)
                save_to_db(dados)
                st.success(f"{len(dados)} hinos salvos com sucesso!")
                st.rerun()

# --- EXIBIÇÃO ---
try:
    res_cat = supabase.table("hinos_categorias").select("*").order("id").execute()
    if res_cat.data:
        df_cat = pd.DataFrame(res_cat.data)
        col1, col2 = st.columns([1, 2])
        
        with col1:
            sel_n1 = st.selectbox("📌 Selecione a Seção:", df_cat['nome_nivel1'])
            cat_id = int(df_cat[df_cat['nome_nivel1'] == sel_n1]['id'].iloc[0])
            
            busca = st.text_input("🔍 Busca rápida (Nome/Número):")
            
            h_db = supabase.table("hinos_conteudos").select("*").eq("categoria_id", cat_id).order("id").execute().data
            if h_db:
                if busca:
                    h_db = [h for h in h_db if busca.lower() in h['nome_nivel2'].lower()]
                
                nomes = [h['nome_nivel2'] for h in h_db]
                if nomes:
                    escolha = st.radio("📑 Lista de Hinos:", nomes)
                    info = next(h for h in h_db if h['nome_nivel2'] == escolha)
                    
                    with col2:
                        st.subheader(info['nome_nivel2'])
                        st.divider()
                        st.text(info['texto_completo'])
    else:
        st.info("💡 Banco vazio. Use o menu lateral para processar o hinário.")
except Exception as e:
    st.error(f"Erro no sistema: {e}")

