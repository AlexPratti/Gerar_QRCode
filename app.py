import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd
import re

# Conexão segura com Supabase
url = st.secrets["URL_SUPABASE"]
key = st.secrets["KEY_SUPABASE"]
supabase = create_client(url, key)

def process_docx(file):
    doc = Document(file)
    # Captura os textos de todos os parágrafos ignorando linhas vazias
    paragraphs = []
    for p in doc.paragraphs:
        txt = p.text.strip()
        if txt:
            paragraphs.append(txt)
    
    data = []
    hinos_mapeados = []
    current_cat = "GERAL"
    
    # --- PASSO 1: EXTRAIR ESTRUTURA DO SUMÁRIO ---
    for text in paragraphs:
        # Identifica linhas do sumário pelos pontinhos guia
        if "...." in text:
            # Remove os pontos e o número da página no fim para limpar o título
            clean_text = re.sub(r'\.+\s*\d+$', '', text).strip()
            
            # REGRA NÍVEL 1: Tudo em CAIXA ALTA e não começa com número
            if clean_text.isupper() and not clean_text[0:1].isdigit():
                current_cat = clean_text
            
            # REGRA NÍVEL 2: Começa com número (Hinos)
            elif clean_text[0:1].isdigit():
                hinos_mapeados.append({"cat": current_cat, "titulo": clean_text})
        
        # Para de ler o sumário quando encontra o conteúdo real (Ex: página 10)
        if text == "ORANTES" and "...." not in text:
            break

    # --- PASSO 2: BUSCAR CONTEÚDO NO CORPO DO TEXTO ---
    conteudos = {}
    for h in hinos_mapeados:
        conteudos[h['titulo']] = []
        
    hino_foco = None

    for text in paragraphs:
        # Se a linha for exatamente um dos títulos achados no sumário, muda o foco
        if text in conteudos:
            hino_foco = text
        elif hino_foco:
            # Se não for outro título, é a letra/cifra do hino atual
            if text not in conteudos:
                # Se encontrar uma nova categoria em caixa alta no corpo, encerra o hino
                if text.isupper() and len(text) < 50 and not text[0:1].isdigit():
                    hino_foco = None
                else:
                    conteudos[hino_foco].append(text)
    
    # --- PASSO 3: MONTAGEM FINAL ---
    for h in hinos_mapeados:
        data.append({
            "n1": h['cat'],
            "n2": h['titulo'],
            "texto": "\n".join(conteudos[h['titulo']])
        })
    return data

def save_to_db(data):
    # Limpa as tabelas para evitar duplicados
    supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
    supabase.table("hinos_categorias").delete().neq("id", 0).execute()
    
    seen_cats = {}
    for item in data:
        cat_name = item['n1']
        # Insere categoria se for nova
        if cat_name not in seen_cats:
            res = supabase.table("hinos_categorias").insert({"nome_nivel1": cat_name}).execute()
            if res.data:
                # Pega o ID gerado pelo Supabase
                seen_cats[cat_name] = res.data[0]['id']
        
        # Insere o hino vinculado à categoria
        if cat_name in seen_cats:
            supabase.table("hinos_conteudos").insert({
                "categoria_id": seen_cats[cat_name],
                "nome_nivel2": item['n2'],
                "texto_completo": item['texto']
            }).execute()

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Hinário Litúrgico", layout="wide")

with st.sidebar:
    st.title("⚙️ Painel Admin")
    arquivo = st.file_uploader("Upload do arquivo .docx", type="docx")
    if st.button("🚀 Processar Hinário"):
        if arquivo:
            with st.spinner("Lendo sumário e hinos..."):
                dados = process_docx(arquivo)
                save_to_db(dados)
                st.success(f"{len(dados)} hinos carregados com sucesso!")
                st.rerun()

# --- EXIBIÇÃO ---
try:
    # Carrega categorias do banco
    res_cat = supabase.table("hinos_categorias").select("*").order("id").execute()
    
    if res_cat.data:
        df_cat = pd.DataFrame(res_cat.data)
        col1, col2 = st.columns([1, 2])
        
        with col1:
            sel_n1 = st.selectbox("📌 1. Selecione a Seção:", df_cat['nome_nivel1'])
            cat_id = int(df_cat[df_cat['nome_nivel1'] == sel_n1]['id'].iloc[0])
            
            busca = st.text_input("🔍 2. Busca rápida (Nome ou Número):")
            
            # Busca hinos da categoria selecionada
            h_db = supabase.table("hinos_conteudos").select("*").eq("categoria_id", cat_id).order("id").execute().data
            
            if h_db:
                if busca:
                    h_db = [h for h in h_db if busca.lower() in h['nome_nivel2'].lower()]
                
                nomes_hinos = [h['nome_nivel2'] for h in h_db]
                if nomes_hinos:
                    escolha = st.radio("📑 3. Escolha o hino:", nomes_hinos)
                    info = next(h for h in h_db if h['nome_nivel2'] == escolha)
                    
                    with col2:
                        st.subheader(info['nome_nivel2'])
                        st.divider()
                        # st.text preserva o alinhamento das cifras e versos
                        st.text(info['texto_completo'])
                else:
                    st.warning("Nenhum hino encontrado.")
    else:
        st.info("💡 Banco de dados vazio. Use o menu lateral para processar o hinário.")

except Exception as e:
    st.error(f"Erro no sistema: {e}")
