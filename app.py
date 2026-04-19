import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd
import re

# Conexão
supabase = create_client(st.secrets["URL_SUPABASE"], st.secrets["KEY_SUPABASE"])

def process_docx(file):
    doc = Document(file)
    data = []
    current_n1 = "GERAL"
    current_n2 = None
    current_text = []

    for para in doc.paragraphs:
        text = para.text.strip()
        
        # 1. Ignorar linhas vazias ou do sumário (pontinhos)
        if not text or "...." in text or text.lower() == "sumário":
            continue

        # 2. Detectar Hinos (Nível 2) - Padrão: "1. Texto" ou "12. Texto"
        # O regex r'^\d+\.\s' procura por dígitos no início da linha seguidos de ponto e espaço
        if re.match(r'^\d+\.\s', text):
            if current_n2:
                data.append({"n1": current_n1, "n2": current_n2, "texto": "\n".join(current_text)})
            
            current_n2 = text
            current_text = []
            continue

        # 3. Detectar Seções (Nível 1) - Padrão: Todo em MAIÚSCULO e sem números no início
        # Ex: ORANTES, PERDÃO, INICIAIS E FINAIS
        if text.isupper() and not text[0].isdigit() and len(text) < 60:
            current_n1 = text
            continue

        # 4. É corpo de texto (versos ou cifras)
        if current_n2:
            current_text.append(text)

    # Adicionar o último hino processado
    if current_n2:
        data.append({"n1": current_n1, "n2": current_n2, "texto": "\n".join(current_text)})
    
    return data

def save_to_db(data):
    # Deleta hinos primeiro, depois categorias (ordem de FK)
    supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
    supabase.table("hinos_categorias").delete().neq("id", 0).execute()
    
    # Pegar categorias únicas na ordem em que aparecem
    categorias_vistas = []
    for item in data:
        if item['n1'] not in categorias_vistas:
            categorias_vistas.append(item['n1'])

    for cat_nome in categorias_vistas:
        # Insere e recupera o ID
        res_cat = supabase.table("hinos_categorias").insert({"nome_nivel1": cat_nome}).execute()
        # No Supabase Python, o dado retornado é uma lista em .data
        cat_id = res_cat.data[0]['id']
        
        hinos_da_cat = [
            {"categoria_id": cat_id, "nome_nivel2": i['n2'], "texto_completo": i['texto']} 
            for i in data if i['n1'] == cat_nome
        ]
        
        if hinos_da_cat:
            supabase.table("hinos_conteudos").insert(hinos_da_cat).execute()

# --- INTERFACE ---
st.set_page_config(page_title="Hinário", layout="wide")

with st.sidebar:
    st.title("⚙️ Sistema")
    arquivo = st.file_uploader("Arquivo .docx", type="docx")
    if st.button("🚀 Processar Tudo") and arquivo:
        with st.spinner("Limpando banco e reprocessando..."):
            dados = process_docx(arquivo)
            if dados:
                save_to_db(dados)
                st.success(f"Carregados {len(dados)} hinos em {len(set(d['n1'] for d in dados))} categorias!")
                st.rerun()
            else:
                st.error("Não encontramos hinos no padrão '1. Título' no arquivo.")

# --- EXIBIÇÃO ---
try:
    res_cat = supabase.table("hinos_categorias").select("*").order("id").execute()
    if res_cat.data:
        df_cat = pd.DataFrame(res_cat.data)
        
        c1, c2 = st.columns([1, 2])
        
        with c1:
            escolha_n1 = st.selectbox("📌 Selecione a Seção:", df_cat['nome_nivel1'])
            id_n1 = int(df_cat[df_cat['nome_nivel1'] == escolha_n1]['id'].iloc[0])
            
            busca = st.text_input("🔍 Busca rápida:")
            
            query = supabase.table("hinos_conteudos").select("*").eq("categoria_id", id_n1).order("id")
            if busca:
                query = query.ilike("nome_nivel2", f"%{busca}%")
            
            hinos_res = query.execute().data
            
            if hinos_res:
                lista_titulos = [h['nome_nivel2'] for h in hinos_res]
                escolha_hino = st.radio("📑 Escolha o hino:", lista_titulos)
                info_hino = next(h for h in hinos_res if h['nome_nivel2'] == escolha_hino)
            else:
                st.warning("Nada encontrado.")
                info_hino = None

        with c2:
            if info_hino:
                st.subheader(info_hino['nome_nivel2'])
                st.divider()
                # st.code ou st.text preserva a diagramação de hinos/cifras
                st.code(info_hino['texto_completo'], language=None)
    else:
        st.info("O banco está vazio. Use o menu lateral para subir o documento.")
except Exception as e:
    st.error(f"Erro: {e}")

