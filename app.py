import streamlit as st
import fitz  # PyMuPDF
import re
from supabase import create_client
import pandas as pd
import io
import base64

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Hinário Visual", layout="wide")

# Conexão Supabase
try:
    supabase = create_client(st.secrets["URL_SUPABASE"], st.secrets["KEY_SUPABASE"])
except:
    st.error("Erro de conexão com Supabase.")
    st.stop()

BUCKET, FILE_PATH = "hinarios", "hinario_atual.pdf"
CATEGORIAS_ALVO = ["ORANTES", "INICIAIS E FINAIS", "PERDÃO", "GLÓRIA", "DEUS NOS FALA", "SALMO", "ACLAMAÇÃO", "OFERTÓRIO", "LOUVOR", "SANTO", "CORDEIRO", "PAZ", "COMUNHÃO", "BÍBLIA", "CRUZ", "LADAINHAS – SEQUÊNCIAS - PROCLAMAÇÕES", "MARIA", "HINOS DIVERSOS", "PRECES"]

# --- FUNÇÕES DE APOIO ---

def process_pdf_fitz(file_bytes):
    data = []
    current_cat = "Sem Categoria"
    try:
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
        st.error(f"Erro no processamento: {e}")
        return []

def save_to_db(data):
    supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
    supabase.table("hinos_categorias").delete().neq("id", 0).execute()
    for cat in CATEGORIAS_ALVO:
        res = supabase.table("hinos_categorias").insert({"nome_nivel1": cat}).execute()
        if res.data:
            res_data = res.data[0] if isinstance(res.data, list) else res.data
            cat_id = res_data['id']
            itens = [{"categoria_id": cat_id, "nome_nivel2": item['n2'], "texto_completo": str(item['pag'])} for item in data if item['n1'] == cat]
            if itens: supabase.table("hinos_conteudos").insert(itens).execute()

# --- CRIAÇÃO DAS ABAS ---
tab_visualizacao, tab_upload = st.tabs(["🎵 Visualizar Hinos", "⬆️ Gerenciar PDF"])

# --- ABA 1: VISUALIZAÇÃO ---
with tab_visualizacao:
    try:
        res_cat = supabase.table("hinos_categorias").select("*").order("nome_nivel1").execute()
        if res_cat.data:
            df_cat = pd.DataFrame(res_cat.data)
            col1, col2 = st.columns(2)
            with col1:
                sel_cat = st.selectbox("Selecione a Categoria", df_cat['nome_nivel1'])
                cat_id = df_cat[df_cat['nome_nivel1'] == sel_cat]['id'].iloc[0]
            
            hinos_res = supabase.table("hinos_conteudos").select("*").eq("categoria_id", int(cat_id)).execute().data
            if hinos_res:
                hinos_ord = sorted(hinos_res, key=lambda x: int(re.search(r'\d+', x['nome_nivel2']).group()) if re.search(r'\d+', x['nome_nivel2']) else 0)
                with col2:
                    sel_hino = st.selectbox("Selecione o Hino", [h['nome_nivel2'] for h in hinos_ord])
                
                # Renderização do Hino
                pdf_res = supabase.storage.from_(BUCKET).download(FILE_PATH)
                if pdf_res:
                    hino_obj = next(h for h in hinos_res if h['nome_nivel2'] == sel_hino)
                    p_num = int(hino_obj['texto_completo']) - 1
                    
                    doc = fitz.open(stream=pdf_res, filetype="pdf")
                    page = doc[p_num]
                    
                    # Lógica de Recorte Dinâmico
                    text_instances = page.search_for(sel_hino)
                    y_ini = text_instances[0].y0 if text_instances else 0
                    
                    # Tenta achar o início do próximo hino para definir o y_fim
                    y_fim = page.rect.height
                    # Extraímos blocos de texto para achar o próximo título na mesma página
                    blocks = page.get_text("blocks")
                    for b in blocks:
                        # Se o bloco está abaixo do título atual e parece um novo título ou categoria
                        if b[1] > y_ini + 10:
                            txt_block = b[4].strip()
                            if re.match(r'^\d+\.', txt_block) or txt_block.upper() in CATEGORIAS_ALVO:
                                y_fim = b[1]
                                break

                    # Renderização com zoom 2x para nitidez
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=fitz.Rect(0, max(0, y_ini-15), page.rect.width, y_fim))
                    img_data = pix.tobytes("png")
                    
                    st.divider()
                    st.image(img_data, use_container_width=True)
                    doc.close()
            else:
                st.info("Nenhum hino encontrado nesta categoria.")
        else:
            st.info("O banco de dados está vazio. Vá na aba 'Gerenciar PDF' e faça o upload.")
    except Exception as e:
        st.error(f"Erro na visualização: {e}")

# --- ABA 2: UPLOAD ---
with tab_upload:
    st.subheader("Configurações do Hinário")
    novo = st.file_uploader("Selecione o novo arquivo PDF", type="pdf")
    
    if st.button("🚀 Atualizar Banco e Arquivo") and novo:
        with st.spinner("Processando... Por favor, não feche a página."):
            bytes_pdf = novo.read()
            
            # 1. Limpa Storage e sobe novo
            try:
                lista = supabase.storage.from_(BUCKET).list()
                if lista: supabase.storage.from_(BUCKET).remove([f['name'] for f in lista])
            except: pass
            
            supabase.storage.from_(BUCKET).upload(
                path=FILE_PATH, 
                file=bytes_pdf, 
                file_options={"x-upsert": "true", "content-type": "application/pdf"}
            )
            
            # 2. Processa estrutura e salva banco
            dados = process_pdf_fitz(bytes_pdf)
            if dados:
                save_to_db(dados)
                st.success("Tudo pronto! O app será reiniciado.")
                st.rerun()
            else:
                st.error("Não foi possível ler os hinos deste PDF.")

    st.divider()
    st.caption("Nota: O processamento pode levar alguns segundos dependendo do número de páginas.")

