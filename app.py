import streamlit as st
import pdfplumber
import re
from supabase import create_client
import pandas as pd

# Conexão
supabase = create_client(st.secrets["URL_SUPABASE"], st.secrets["KEY_SUPABASE"])

CATEGORIAS_ALVO = [
    "ORANTES", "INICIAIS E FINAIS", "PERDÃO", "GLÓRIA", "DEUS NOS FALA", 
    "SALMO", "ACLAMAÇÃO", "OFERTÓRIO", "LOUVOR", "SANTO", "CORDEIRO", 
    "PAZ", "COMUNHÃO", "BÍBLIA", "CRUZ", "LADAINHAS – SEQUÊNCIAS - PROCLAMAÇÕES", 
    "MARIA", "PRECES"
]

def process_pdf(file):
    data = []
    current_n1 = "Sem Categoria"
    current_n2 = None
    current_text = []

    with pdfplumber.open(file) as pdf:
        progresso = st.progress(0)
        for i, page in enumerate(pdf.pages):
            # layout=True é vital para manter cifras sobre as letras
            text = page.extract_text(layout=True)
            if not text: continue
            
            linhas = text.split('\n')
            for linha in linhas:
                texto_limpo = linha.strip()
                if not texto_limpo or "Sumário" in texto_limpo: continue

                # Nível 1 - Categorias
                if texto_limpo.upper() in CATEGORIAS_ALVO:
                    if current_n2:
                        data.append({"n1": current_n1, "n2": current_n2, "texto": "\n".join(current_text)})
                    current_n1 = texto_limpo.upper()
                    current_n2 = None 
                    current_text = []
                    data.append({"n1": current_n1, "n2": None, "texto": ""})
                    continue

                # Nível 2 - Títulos dos Hinos (Começa com número)
                if re.match(r'^\d+\.', texto_limpo):
                    if current_n2:
                        data.append({"n1": current_n1, "n2": current_n2, "texto": "\n".join(current_text)})
                    current_n2 = texto_limpo
                    current_text = []
                    
                elif current_n2:
                    if not texto_limpo.isdigit():
                        # Guardamos a 'linha' integral para preservar espaços das cifras
                        current_text.append(linha)

            progresso.progress((i + 1) / len(pdf.pages))

    if current_n2:
        data.append({"n1": current_n1, "n2": current_n2, "texto": "\n".join(current_text)})
    return data
def save_to_db(data):
    # Limpeza total para evitar duplicatas
    supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
    supabase.table("hinos_categorias").delete().neq("id", 0).execute()
    
    categorias_encontradas = sorted(list(set([item['n1'] for item in data])))
    for cat_nome in categorias_encontradas:
        res = supabase.table("hinos_categorias").insert({"nome_nivel1": cat_nome}).execute()
        
        # Correção no acesso ao ID do Supabase
        if res.data:
            cat_id = res.data[0]['id']
            
            itens = [
                {"categoria_id": cat_id, "nome_nivel2": item['n2'], "texto_completo": item['texto']} 
                for item in data if item['n1'] == cat_nome and item['n2'] is not None
            ]
            if itens:
                supabase.table("hinos_conteudos").insert(itens).execute()

# --- INTERFACE ---
st.set_page_config(page_title="Hinário", layout="wide")

with st.expander("⬆️ Upload PDF"):
    arquivo = st.file_uploader("Arquivo PDF", type="pdf")
    if st.button("Atualizar Banco") and arquivo:
        dados = process_pdf(arquivo)
        save_to_db(dados)
        st.success("Banco atualizado!")
        st.rerun()

# --- EXIBIÇÃO ---
try:
    res_cat = supabase.table("hinos_categorias").select("*").order("nome_nivel1").execute()
    if res_cat.data:
        df_cat = pd.DataFrame(res_cat.data)
        c1, c2 = st.columns(2)
        with c1:
            escolha_n1 = st.selectbox("Categoria", df_cat['nome_nivel1'])
            # Filtro robusto para pegar o ID da categoria selecionada
            id_n1 = int(df_cat[df_cat['nome_nivel1'] == escolha_n1]['id'].values[0])
        
        # Busca hinos vinculados ao ID da categoria
        res_hinos = supabase.table("hinos_conteudos").select("*").eq("categoria_id", id_n1).execute()
        hinos = res_hinos.data

        if hinos:
            hino_sel = st.radio("Hino:", [h['nome_nivel2'] for h in hinos])
            conteudo = next(h for h in hinos if h['nome_nivel2'] == hino_sel)
            
            st.markdown("---")
            # CSS final para fonte monoespaçada e preservação de espaços/quebras
            st.markdown(f"""
            <div style="background-color: white; padding: 20px; border: 1px solid #ddd; border-radius: 8px; overflow-x: auto;">
                <pre style="font-family: 'Courier New', Courier, monospace; font-size: 16px; white-space: pre; color: #1e1e1e; line-height: 1.2;">{conteudo['texto_completo']}</pre>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.warning("Nenhum hino nesta categoria.")
    else:
        st.info("Aguardando upload do primeiro arquivo...")
except Exception as e:
    # Mostra o erro real se algo falhar
    st.error(f"Erro ao carregar dados: {e}")
