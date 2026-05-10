import streamlit as st
import fitz  # PyMuPDF: Mais robusto que pdfplumber
import re
from supabase import create_client
import pandas as pd
import io
import base64

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Hinário Visual", layout="wide")

try:
    supabase = create_client(st.secrets["URL_SUPABASE"], st.secrets["KEY_SUPABASE"])
except:
    st.error("Erro de conexão com Supabase.")
    st.stop()

BUCKET, FILE_PATH = "hinarios", "hinario_atual.pdf"
CATEGORIAS_ALVO = ["ORANTES", "INICIAIS E FINAIS", "PERDÃO", "GLÓRIA", "DEUS NOS FALA", "SALMO", "ACLAMAÇÃO", "OFERTÓRIO", "LOUVOR", "SANTO", "CORDEIRO", "PAZ", "COMUNHÃO", "BÍBLIA", "CRUZ", "LADAINHAS – SEQUÊNCIAS - PROCLAMAÇÕES", "MARIA", "HINOS DIVERSOS", "PRECES"]

def process_pdf_fitz(file_bytes):
    """Processamento usando PyMuPDF para evitar erros de formato"""
    data = []
    current_cat = "Sem Categoria"
    try:
        # Abre o PDF a partir da memória
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        progresso = st.progress(0)
        total_pags = len(doc)
        
        for i in range(total_pags):
            page = doc[i]
            text = page.get_text()
            if not text: continue
            
            for line in text.split('\n'):
                t_limpo = line.strip()
                if t_limpo.upper() in CATEGORIAS_ALVO:
                    current_cat = t_limpo.upper()
                elif re.match(r'^\d+\.', t_limpo) and t_limpo == t_limpo.upper():
                    data.append({"n1": current_cat, "n2": t_limpo, "pag": i + 1})
            progresso.progress((i + 1) / total_pags)
        
        doc.close()
        return data
    except Exception as e:
        st.error(f"Erro no processamento PyMuPDF: {e}")
        return []

def save_to_db(data):
    supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
    supabase.table("hinos_categorias").delete().neq("id", 0).execute()
    for cat in CATEGORIAS_ALVO:
        res = supabase.table("hinos_categorias").insert({"nome_nivel1": cat}).execute()
        if res.data:
            cat_id = res.data[0]['id'] if isinstance(res.data, list) else res.data['id']
            itens = [{"categoria_id": cat_id, "nome_nivel2": item['n2'], "texto_completo": str(item['pag'])} for item in data if item['n1'] == cat]
            if itens: supabase.table("hinos_conteudos").insert(itens).execute()

# --- INTERFACE: UPLOAD ---
with st.expander("⬆️ Upload PDF"):
    novo = st.file_uploader("Selecione o arquivo", type="pdf")
    if st.button("Atualizar Banco") and novo:
        bytes_pdf = novo.read()
        # Upload para o storage
        supabase.storage.from_(BUCKET).upload(path=FILE_PATH, file=bytes_pdf, file_options={"x-upsert": "true", "content-type": "application/pdf"})
        # Processamento
        dados = process_pdf_fitz(bytes_pdf)
        if dados:
            save_to_db(dados)
            st.success("Sincronizado!")
            st.rerun()

# --- INTERFACE: EXIBIÇÃO ---
try:
    res_cat = supabase.table("hinos_categorias").select("*").order("nome_nivel1").execute()
    if res_cat.data:
        df_cat = pd.DataFrame(res_cat.data)
        col1, col2 = st.columns(2)
        with col1:
            sel_cat = st.selectbox("Categoria", df_cat['nome_nivel1'])
            cat_id = df_cat[df_cat['nome_nivel1'] == sel_cat]['id'].iloc[0]
        
        hinos = supabase.table("hinos_conteudos").select("*").eq("categoria_id", int(cat_id)).execute().data
        if hinos:
            hinos_ord = sorted(hinos, key=lambda x: int(re.search(r'\d+', x['nome_nivel2']).group()) if re.search(r'\d+', x['nome_nivel2']) else 0)
            with col2:
                sel_hino = st.selectbox("Hino", [h['nome_nivel2'] for h in hinos_ord])
            
            # Download e Renderização
            pdf_res = supabase.storage.from_(BUCKET).download(FILE_PATH)
            if pdf_res:
                hino_obj = next(h for h in hinos if h['nome_nivel2'] == sel_hino)
                p_num = int(hino_obj['texto_completo']) - 1 # fitz usa índice 0
                
                # Abre para recortar
                doc = fitz.open(stream=pdf_res, filetype="pdf")
                page = doc[p_num]
                
                # Busca as coordenadas do título para o recorte
                text_instances = page.search_for(sel_hino)
                y_ini = text_instances[0].y0 if text_instances else 0
                
                # Renderiza a página (zoom de 2x para nitidez)
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat, clip=fitz.Rect(0, y_ini-10, page.rect.width, page.rect.height))
                img_data = pix.tobytes("png")
                
                st.divider()
                st.image(img_data, use_container_width=True)
                doc.close()
    else:
        st.info("Aguardando upload...")
except Exception as e:
    st.error(f"Erro na exibição: {e}")
