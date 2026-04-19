import streamlit as st
import pdfplumber
import re
from supabase import create_client
import io
from PIL import Image

# Conexão
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
    
    # Abrimos o PDF para mapear onde cada hino começa e termina
    with pdfplumber.open(file) as pdf:
        progresso = st.progress(0)
        total_paginas = len(pdf.pages)
        
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text: continue
            
            linhas = text.split('\n')
            for linha in linhas:
                texto_limpo = linha.strip()
                
                # Identifica Categoria (Nível 1)
                if texto_limpo.upper() in CATEGORIAS_ALVO:
                    current_n1 = texto_limpo.upper()
                    continue

                # Identifica Hino (Nível 2)
                if re.match(r'^\d+\.', texto_limpo):
                    # Se já vínhamos de um hino, o fim dele é a página anterior ou atual
                    if current_n2:
                        data.append({
                            "n1": current_n1, 
                            "n2": current_n2, 
                            "pag_inicio": start_page, 
                            "pag_fim": i + 1 # Página atual
                        })
                    
                    current_n2 = texto_limpo
                    start_page = i + 1 # Registra onde este hino começa
            
            progresso.progress((i + 1) / total_paginas)

        # Salva o último hino
        if current_n2:
            data.append({
                "n1": current_n1, 
                "n2": current_n2, 
                "pag_inicio": start_page, 
                "pag_fim": total_paginas
            })
            
    return data
def save_to_db(data):
    supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
    supabase.table("hinos_categorias").delete().neq("id", 0).execute()
    
    for cat_nome in CATEGORIAS_ALVO:
        res = supabase.table("hinos_categorias").insert({"nome_nivel1": cat_nome}).execute()
        if res.data:
            cat_id = res.data['id']
            
            # Note que agora salvamos as páginas em vez do texto
            itens = [
                {
                    "categoria_id": cat_id, 
                    "nome_nivel2": item['n2'], 
                    "pag_inicio": item['pag_inicio'],
                    "pag_fim": item['pag_fim']
                } 
                for item in data if item['n1'] == cat_nome
            ]
            if itens:
                supabase.table("hinos_conteudos").insert(itens).execute()

# --- INTERFACE ---
st.set_page_config(page_title="Hinário Visual", layout="wide")

with st.sidebar:
    arquivo = st.file_uploader("Upload do PDF", type="pdf")
    if st.button("Sincronizar Banco") and arquivo:
        dados = process_pdf_as_images(arquivo)
        save_to_db(dados)
        st.success("Sincronizado!")

try:
    res_cat = supabase.table("hinos_categorias").select("*").order("nome_nivel1").execute()
    if res_cat.data and arquivo:
        df_cat = pd.DataFrame(res_cat.data)
        col1, col2 = st.columns(2)
        with col1:
            escolha_n1 = st.selectbox("Categoria", df_cat['nome_nivel1'])
            id_n1 = int(df_cat[df_cat['nome_nivel1'] == escolha_n1]['id'].iloc)
        
        hinos = supabase.table("hinos_conteudos").select("*").eq("categoria_id", id_n1).execute().data

        if hinos:
            hino_sel = st.selectbox("Escolha o hino:", [h['nome_nivel2'] for h in hinos])
            dados_hino = next(h for h in hinos if h['nome_nivel2'] == hino_sel)
            
            st.divider()
            
            # --- EXIBIÇÃO POR "FOTO" ---
            with pdfplumber.open(arquivo) as pdf:
                # Percorre o intervalo de páginas do hino (início ao fim)
                for p_num in range(dados_hino['pag_inicio'], dados_hino['pag_fim'] + 1):
                    page = pdf.pages[p_num - 1]
                    # Converte a página em imagem (foto)
                    img = page.to_image(resolution=150).original
                    st.image(img, use_container_width=True, caption=f"Página {p_num}")
except Exception as e:
    st.info("Faça o upload do PDF no menu lateral para visualizar.")
