import streamlit as st
import pdfplumber
import re
from supabase import create_client
import pandas as pd

# Conexão original mantida
supabase = create_client(st.secrets["URL_SUPABASE"], st.secrets["KEY_SUPABASE"])

CATEGORIAS_ALVO = [
    "ORANTES", "INICIAIS E FINAIS", "PERDÃO", "GLÓRIA", "DEUS NOS FALA", 
    "SALMO", "ACLAMAÇÃO", "OFERTÓRIO", "LOUVOR", "SANTO", "CORDEIRO", 
    "PAZ", "COMUNHÃO", "BÍBLIA", "CRUZ", "LADAINHAS – SEQUÊNCIAS - PROCLAMAÇÕES", 
    "MARIA", "PRECES"
]

def process_pdf_as_images(file):
    data = []
    current_n1 = "Sem Categoria"
    current_n2 = None
    start_page = 0
    
    with pdfplumber.open(file) as pdf:
        progresso = st.progress(0)
        total_paginas = len(pdf.pages)
        
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text: continue
            
            linhas = text.split('\n')
            for linha in linhas:
                texto_limpo = linha.strip()
                
                if texto_limpo.upper() in CATEGORIAS_ALVO:
                    current_n1 = texto_limpo.upper()
                    continue

                # Identifica Hino (Ex: 3. HINO)
                if re.match(r'^\d+\.', texto_limpo):
                    if current_n2:
                        # O fim do hino anterior é exatamente onde este começa
                        data.append({
                            "n1": current_n1, 
                            "n2": current_n2, 
                            "pag_inicio": start_page, 
                            "pag_fim": i + 1 
                        })
                    
                    current_n2 = texto_limpo
                    start_page = i + 1
            
            progresso.progress((i + 1) / total_paginas)

        if current_n2:
            data.append({
                "n1": current_n1, "n2": current_n2, 
                "pag_inicio": start_page, "pag_fim": total_paginas
            })
    return data
def save_to_db(data):
    supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
    supabase.table("hinos_categorias").delete().neq("id", 0).execute()
    
    for cat_nome in CATEGORIAS_ALVO:
        res = supabase.table("hinos_categorias").insert({"nome_nivel1": cat_nome}).execute()
        if res.data and len(res.data) > 0:
            cat_id = res.data[0]['id'] # Ajuste para pegar ID da lista
            
            itens = [
                {
                    "categoria_id": cat_id, 
                    "nome_nivel2": item['n2'], 
                    "texto_completo": f"{item['pag_inicio']}-{item['pag_fim']}" 
                } 
                for item in data if item['n1'] == cat_nome
            ]
            if itens:
                supabase.table("hinos_conteudos").insert(itens).execute()

# --- INTERFACE ---
st.set_page_config(page_title="Hinário Visual", layout="wide")

with st.expander("⬆️ Upload PDF"):
    arquivo = st.file_uploader("Selecione o arquivo", type="pdf")
    if st.button("Atualizar Banco") and arquivo:
        dados = process_pdf_as_images(arquivo)
        save_to_db(dados)
        st.success("Sincronizado!")
        st.rerun()

try:
    res_cat = supabase.table("hinos_categorias").select("*").order("nome_nivel1").execute()
    if res_cat.data and arquivo:
        df_cat = pd.DataFrame(res_cat.data)
        c1, c2 = st.columns(2)
        
        with c1:
            escolha_n1 = st.selectbox("Categoria", df_cat['nome_nivel1'], key="cat_select")
            id_n1 = int(df_cat[df_cat['nome_nivel1'] == escolha_n1]['id'].iloc[0])
        
        # Busca hinos e usa uma chave (key) dinâmica para resetar o radio/selectbox
        hinos = supabase.table("hinos_conteudos").select("*").eq("categoria_id", id_n1).execute().data

        if hinos:
            # Ordenar hinos numericamente para não misturar
            hinos_ordenados = sorted(hinos, key=lambda x: int(re.search(r'\d+', x['nome_nivel2']).group()))
            titulos = [h['nome_nivel2'] for h in hinos_ordenados]
            
            # Usamos o nome da categoria na key para forçar o Streamlit a limpar a seleção anterior
            hino_sel = st.selectbox("Escolha o Hino:", titulos, key=f"hino_{escolha_n1}")
            
            dados_hino = next(h for h in hinos if h['nome_nivel2'] == hino_sel)
            pag_str = dados_hino['texto_completo'].split('-')
            p_ini, p_fim = int(pag_str[0]), int(pag_str[1])
            
            st.divider()
            with pdfplumber.open(arquivo) as pdf:
                # Se o hino começa e termina na mesma página, mostra só uma
                # Se for hino longo, mostra as páginas necessárias
                for p_num in range(p_ini, p_fim + 1):
                    img = pdf.pages[p_num - 1].to_image(resolution=200).original
                    st.image(img, use_container_width=True)
    else:
        st.info("Aguardando PDF...")
except Exception as e:
    st.error(f"Selecione uma categoria válida para carregar os hinos.")
