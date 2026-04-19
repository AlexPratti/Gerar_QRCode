import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd

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
        if not text or "............" in text: continue # Ignora linhas vazias ou do sumário

        # LÓGICA NÍVEL 1: Texto TODO em maiúsculo, sem começar com número, e sem ser muito longo
        # Ex: ORANTES, PERDÃO, INICIAIS E FINAIS
        if text.isupper() and not text[0].isdigit() and len(text) < 50:
            current_n1 = text
            # Se mudou de seção, precisamos resetar o hino atual
            if current_n2:
                data.append({"n1": current_n1_old, "n2": current_n2, "texto": "\n".join(current_text)})
                current_n2 = None
            current_n1_old = current_n1
            
        # LÓGICA NÍVEL 2: Começa com número e ponto (ex: 1. VENHA A NÓS)
        elif text[0:1].isdigit() and "." in text[0:5]:
            # Salva o hino anterior se houver
            if current_n2:
                data.append({"n1": current_n1, "n2": current_n2, "texto": "\n".join(current_text)})
            
            current_n2 = text
            current_text = []
            
        # CORPO DO TEXTO (Versos e Cifras)
        else:
            if current_n2:
                current_text.append(text)

    # Adiciona o último hino do documento
    if current_n2:
        data.append({"n1": current_n1, "n2": current_n2, "texto": "\n".join(current_text)})
    
    return data

def save_to_db(data):
    # Limpa as tabelas com a ordem correta para não dar erro de vínculo
    supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
    supabase.table("hinos_categorias").delete().neq("id", 0).execute()
    
    # Mapeia categorias únicas
    categorias = sorted(list(set([item['n1'] for item in data])))
    for cat_nome in categorias:
        res = supabase.table("hinos_categorias").insert({"nome_nivel1": cat_nome}).execute()
        cat_id = res.data[0]['id'] # Ajuste para acessar o ID corretamente
        
        # Prepara lista de hinos para inserção em massa
        itens = [
            {"categoria_id": cat_id, "nome_nivel2": i['n2'], "texto_completo": i['texto']} 
            for i in data if i['n1'] == cat_nome
        ]
        if itens:
            supabase.table("hinos_conteudos").insert(itens).execute()

# --- INTERFACE ---
st.set_page_config(page_title="Hinário Litúrgico", layout="wide")

with st.sidebar:
    st.title("⚙️ Configurações")
    arquivo = st.file_uploader("Upload do Hinário (.docx)", type="docx")
    if st.button("🚀 Atualizar Hinário Completo") and arquivo:
        with st.spinner("Lendo e organizando hinos..."):
            dados = process_docx(arquivo)
            save_to_db(dados)
            st.success(f"Hinário atualizado! {len(dados)} hinos carregados.")
            st.rerun()

# --- EXIBIÇÃO ---
try:
    res_cat = supabase.table("hinos_categorias").select("*").order("nome_nivel1").execute()
    if res_cat.data:
        df_cat = pd.DataFrame(res_cat.data)
        
        col1, col2 = st.columns([1, 2]) # Coluna do texto é maior
        
        with col1:
            escolha_n1 = st.selectbox("📌 1. Seção:", df_cat['nome_nivel1'])
            id_n1 = int(df_cat[df_cat['nome_nivel1'] == escolha_n1]['id'].iloc[0])
            
            busca = st.text_input("🔍 2. Buscar hino:")
            
            query = supabase.table("hinos_conteudos").select("*").eq("categoria_id", id_n1).order("nome_nivel2")
            if busca:
                query = query.ilike("nome_nivel2", f"%{busca}%")
            
            hinos = query.execute().data
            
            if hinos:
                titulos = [h['nome_nivel2'] for h in hinos]
                # Radio com altura limitada para não esticar a tela
                escolha_hino = st.radio("📑 3. Escolha o hino:", titulos)
                info_hino = next(h for h in hinos if h['nome_nivel2'] == escolha_hino)
            else:
                st.warning("Nenhum hino nesta seção.")
                info_hino = None

        with col2:
            if info_hino:
                st.subheader(info_hino['nome_nivel2'])
                st.markdown("---")
                # st.text preserva espaços e quebras de linha (ideal para cifras)
                st.text(info_hino['texto_completo']) 
    else:
        st.info("💡 Bem-vindo! Use o menu lateral para carregar o hinário pela primeira vez.")
except Exception as e:
    st.error(f"Erro no banco: {e}")
