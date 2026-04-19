import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd

# Conexão
supabase = create_client(st.secrets["URL_SUPABASE"], st.secrets["KEY_SUPABASE"])

def process_docx(file):
    doc = Document(file)
    data = []
    current_n1 = "OUTROS"
    current_n2 = None
    current_text = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text: continue

        # LÓGICA DE NÍVEL 1: Texto todo em maiúsculo e curto (ex: ORANTES, PERDÃO)
        # Ou se tiver o estilo de Título 1
        if (text.isupper() and len(text) < 40) or 'Heading 1' in para.style.name or 'Título 1' in para.style.name:
            current_n1 = text
            current_n2 = None
            
        # LÓGICA DE NÍVEL 2: Começa com número seguido de ponto (ex: 1. VENHA A NÓS...)
        elif text[0:1].isdigit() and ". " in text[0:5]:
            if current_n2:
                data.append({"n1": current_n1, "n2": current_n2, "texto": "\n".join(current_text)})
            current_n2 = text
            current_text = []
            
        # CORPO DO TEXTO
        else:
            if current_n2:
                current_text.append(text)

    # Adiciona o último hino
    if current_n2:
        data.append({"n1": current_n1, "n2": current_n2, "texto": "\n".join(current_text)})
    return data

def save_to_db(data):
    supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
    supabase.table("hinos_categorias").delete().neq("id", 0).execute()
    
    categorias = sorted(list(set([item['n1'] for item in data])))
    for cat_nome in categorias:
        res = supabase.table("hinos_categorias").insert({"nome_nivel1": cat_nome}).execute()
        cat_id = res.data[0]['id']
        
        itens = [{"categoria_id": cat_id, "nome_nivel2": i['n2'], "texto_completo": i['texto']} 
                 for i in data if i['n1'] == cat_nome]
        supabase.table("hinos_conteudos").insert(itens).execute()

# --- INTERFACE ---
st.set_page_config(page_title="Hinário Litúrgico", layout="wide")

with st.sidebar:
    st.title("⚙️ Painel de Controle")
    arquivo = st.file_uploader("Upload do Hinário (.docx)", type="docx")
    if st.button("🚀 Processar e Salvar no Banco") and arquivo:
        with st.spinner("Lendo documento..."):
            dados = process_docx(arquivo)
            save_to_db(dados)
            st.success(f"Sucesso! {len(dados)} hinos carregados.")
            st.rerun()

# --- EXIBIÇÃO ---
try:
    res_cat = supabase.table("hinos_categorias").select("*").order("nome_nivel1").execute()
    if res_cat.data:
        df_cat = pd.DataFrame(res_cat.data)
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            escolha_n1 = st.selectbox("📌 1. Escolha a Seção (Nível 1):", df_cat['nome_nivel1'])
            id_n1 = int(df_cat[df_cat['nome_nivel1'] == escolha_n1]['id'].iloc[0])
            
            busca = st.text_input("🔍 2. Buscar por hino ou número:")
            
            query = supabase.table("hinos_conteudos").select("*").eq("categoria_id", id_n1).order("nome_nivel2")
            if busca:
                query = query.ilike("nome_nivel2", f"%{busca}%")
            
            hinos = query.execute().data
            
            if hinos:
                titulos = [h['nome_nivel2'] for h in hinos]
                escolha_hino = st.radio("📑 3. Selecione o hino:", titulos)
                info_hino = next(h for h in hinos if h['nome_nivel2'] == escolha_hino)
            else:
                st.warning("Nenhum hino encontrado.")
                info_hino = None

        with col2:
            if info_hino:
                st.subheader(info_hino['nome_nivel2'])
                st.divider()
                # Exibe o texto respeitando as quebras de linha e cifras
                st.text(info_hino['texto_completo']) 
    else:
        st.warning("O banco de dados está vazio. Use o menu lateral para subir o arquivo.")
except Exception as e:
    st.error(f"Erro na conexão: {e}")
