import streamlit as st
from docx import Document
from supabase import create_client
import pandas as pd
import re

# Conexão
supabase = create_client(st.secrets["URL_SUPABASE"], st.secrets["KEY_SUPABASE"])

def process_docx_by_summary(file):
    doc = Document(file)
    data = []
    
    # 1. Primeiro passamos para identificar a estrutura via Sumário
    # Buscamos o padrão "TITULO ............. PAGINA"
    summary_data = []
    current_cat = "GERAL"
    
    # Regex para detectar hinos no sumário (ex: 1. NOME ... 10)
    re_hino_summary = re.compile(r'^(\d+[\.\s].+?)\s?\.+\s?\d+$')
    # Regex para categorias (Texto em CAIXA ALTA sozinho ou com pontinhos)
    re_cat_summary = re.compile(r'^([A-ZÇÃÕÉÍÓÚ\s]+)\s?\.+\s?\d+$')

    all_paragraphs =
    
    # Passo A: Extrair estrutura do Sumário
    hinos_na_ordem = []
    for text in all_paragraphs:
        # Se chegamos na página 10 (onde começam os hinos no seu PDF), paramos de ler o sumário
        if text.startswith("ORANTES") and "...." not in text: 
            break
            
        cat_match = re_cat_summary.match(text)
        hino_match = re_hino_summary.match(text)
        
        if cat_match and not hino_match:
            current_cat = cat_match.group(1).strip()
        elif hino_match:
            hino_titulo = hino_match.group(1).strip()
            hinos_na_ordem.append({"n1": current_cat, "n2": hino_titulo})

    # Passo B: Capturar o conteúdo dos hinos no corpo do documento
    # Vamos criar um dicionário de conteúdos
    conteudos = {}
    current_hino_find = None
    buffer_text = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text: continue
        
        # Se a linha for exatamente um dos títulos que achamos no sumário
        if any(h['n2'] == text for h in hinos_na_ordem):
            if current_hino_find:
                conteudos[current_hino_find] = "\n".join(buffer_text)
            
            current_hino_find = text
            buffer_text = []
        elif current_hino_find:
            buffer_text.append(text)
            
    # Salva o último
    if current_hino_find:
        conteudos[current_hino_find] = "\n".join(buffer_text)

    # Passo C: Unir estrutura + conteúdo
    final_data = []
    for h in hinos_na_ordem:
        final_data.append({
            "n1": h['n1'],
            "n2": h['n2'],
            "texto": conteudos.get(h['n2'], "Texto não localizado no corpo do documento.")
        })
        
    return final_data

def save_to_db(data):
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
st.set_page_config(page_title="Hinário", layout="wide")

with st.sidebar:
    st.title("⚙️ Admin")
    arquivo = st.file_uploader("Arquivo Hinário (.docx)", type="docx")
    if st.button("🚀 Processar via Sumário") and arquivo:
        with st.spinner("Lendo sumário e extraindo letras..."):
            dados = process_docx_by_summary(arquivo)
            if dados:
                save_to_db(dados)
                st.success(f"Carregados {len(dados)} hinos com sucesso!")
                st.rerun()
            else:
                st.error("Erro ao ler a estrutura do sumário.")

# --- EXIBIÇÃO ---
try:
    res_cat = supabase.table("hinos_categorias").select("*").order("id").execute()
    if res_cat.data:
        df_cat = pd.DataFrame(res_cat.data)
        col1, col2 = st.columns([1, 2])
        
        with col1:
            escolha_n1 = st.selectbox("📌 Seção:", df_cat['nome_nivel1'])
            cat_id = int(df_cat[df_cat['nome_nivel1'] == escolha_n1]['id'].iloc[0])
            
            busca = st.text_input("🔍 Busca rápida:")
            hinos_res = supabase.table("hinos_conteudos").select("*").eq("categoria_id", cat_id).order("id").execute().data
            
            if hinos_res:
                if busca:
                    hinos_res = [h for h in hinos_res if busca.lower() in h['nome_nivel2'].lower()]
                
                lista_titulos = [h['nome_nivel2'] for h in hinos_res]
                if lista_titulos:
                    hino_nome = st.radio("📑 Selecione o hino:", lista_titulos)
                    hino_info = next(h for h in hinos_res if h['nome_nivel2'] == hino_nome)
                    
                    with col2:
                        st.subheader(hino_info['nome_nivel2'])
                        st.divider()
                        st.text(hino_info['texto_completo'])
                else:
                    st.warning("Nenhum hino encontrado.")
    else:
        st.info("Banco vazio. Suba o arquivo no menu lateral.")
except Exception as e:
    st.error(f"Erro: {e}")
