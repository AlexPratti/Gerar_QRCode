import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd
import re

# Conexão segura
supabase = create_client(st.secrets["URL_SUPABASE"], st.secrets["KEY_SUPABASE"])

def process_docx(file):
    doc = Document(file)
    # Linha 12 corrigida: Captura todos os parágrafos com texto
    paragraphs =
    
    data = []
    hinos_mapeados = []
    current_cat = "GERAL"
    
    # 1. VARREDURA DO SUMÁRIO
    for text in paragraphs:
        # Identifica se a linha pertence ao sumário (presença de pontos guia)
        if "...." in text:
            # Limpa o texto removendo os pontos e o número da página
            clean_text = re.sub(r'\.+\s*\d+$', '', text).strip()
            
            # Regra Nível 2: Começa com número
            if clean_text[0:1].isdigit():
                hinos_mapeados.append({"cat": current_cat, "titulo": clean_text})
            # Regra Nível 1: Tudo em CAIXA ALTA e não começa com número
            elif clean_text.isupper():
                current_cat = clean_text
        
        # Para de ler o sumário quando encontra o início real do conteúdo
        if text == "ORANTES" and "...." not in text:
            break

    # 2. CAPTURA DO CONTEÚDO (Corpo do Texto)
    conteudos = {h['titulo']: [] for h in hinos_mapeados}
    hino_foco = None

    for text in paragraphs:
        if text in conteudos:
            hino_foco = text
        elif hino_foco:
            # Se a linha não for outro título de hino, adiciona ao corpo
            if text not in conteudos:
                conteudos[hino_foco].append(text)
    
    # 3. MONTAGEM FINAL
    for h in hinos_mapeados:
        data.append({
            "n1": h['cat'],
            "n2": h['titulo'],
            "texto": "\n".join(conteudos[h['titulo']])
        })
    return data

def save_to_db(data):
    # Limpa dados antigos para evitar duplicidade ou conflitos
    supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
    supabase.table("hinos_categorias").delete().neq("id", 0).execute()
    
    seen_cats = {}
    for item in data:
        cat_name = item['n1']
        if cat_name not in seen_cats:
            res = supabase.table("hinos_categorias").insert({"nome_nivel1": cat_name}).execute()
            if res.data:
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
    st.title("⚙️ Administração")
    arquivo = st.file_uploader("Upload do Hinário (.docx)", type="docx")
    if st.button("🚀 Processar Hinário"):
        if arquivo:
            with st.spinner("Extraindo dados..."):
                dados = process_docx(arquivo)
                save_to_db(dados)
                st.success(f"{len(dados)} hinos carregados com sucesso!")
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
            
            busca = st.text_input("🔍 Busca rápida:")
            hinos_db = supabase.table("hinos_conteudos").select("*").eq("categoria_id", cat_id).order("id").execute().data
            
            if hinos_db:
                if busca:
                    hinos_db = [h for h in hinos_db if busca.lower() in h['nome_nivel2'].lower()]
                
                nomes = [h['nome_nivel2'] for h in hinos_db]
                if nomes:
                    escolha = st.radio("📑 Escolha o hino:", nomes)
                    info = next(h for h in hinos_db if h['nome_nivel2'] == escolha)
                    with col2:
                        st.subheader(info['nome_nivel2'])
                        st.divider()
                        st.text(info['texto_completo'])
    else:
        st.info("💡 Banco de dados vazio. Faça o upload no menu lateral.")
except Exception as e:
    st.error(f"Erro no carregamento: {e}")
