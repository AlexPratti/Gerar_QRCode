import streamlit as st
import pdfplumber
import re
from supabase import create_client
import pandas as pd
import io
import base64

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Hinário Visual", layout="wide")

try:
    supabase = create_client(st.secrets["URL_SUPABASE"], st.secrets["KEY_SUPABASE"])
except Exception as e:
    st.error(f"Erro de conexão: {e}")
    st.stop()

BUCKET = "hinarios"
FILE_PATH = "hinario_atual.pdf"
CATEGORIAS_ALVO = ["ORANTES", "INICIAIS E FINAIS", "PERDÃO", "GLÓRIA", "DEUS NOS FALA", "SALMO", "ACLAMAÇÃO", "OFERTÓRIO", "LOUVOR", "SANTO", "CORDEIRO", "PAZ", "COMUNHÃO", "BÍBLIA", "CRUZ", "LADAINHAS – SEQUÊNCIAS - PROCLAMAÇÕES", "MARIA", "HINOS DIVERSOS", "PRECES"]

def process_pdf_simple(file_bytes):
    data = []
    current_n1 = "Sem Categoria"
    try:
        # Força a criação de um novo buffer para o processamento inicial
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            progresso = st.progress(0)
            total = len(pdf.pages)
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if not text: continue
                for line in text.split('\n'):
                    t_limpo = line.strip()
                    if t_limpo.upper() in CATEGORIAS_ALVO:
                        current_n1 = t_limpo.upper()
                    elif re.match(r'^\d+\.', t_limpo) and t_limpo == t_limpo.upper():
                        data.append({"n1": current_n1, "n2": t_limpo, "pag": i + 1})
                progresso.progress((i + 1) / total)
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
            # Pega o ID independente se vier como lista ou dicionário
            res_data = res.data[0] if isinstance(res.data, list) else res.data
            cat_id = res_data['id']
            itens = [{"categoria_id": cat_id, "nome_nivel2": item['n2'], "texto_completo": str(item['pag'])} for item in data if item['n1'] == cat]
            if itens: supabase.table("hinos_conteudos").insert(itens).execute()

# --- INTERFACE: UPLOAD ---
with st.expander("⬆️ Upload PDF"):
    novo = st.file_uploader("Selecione o arquivo", type="pdf")
    if st.button("Atualizar Banco") and novo:
        b_up = novo.read()
        try:
            lista = supabase.storage.from_(BUCKET).list()
            if lista: supabase.storage.from_(BUCKET).remove([f['name'] for f in lista])
        except: pass
        supabase.storage.from_(BUCKET).upload(path=FILE_PATH, file=b_up, file_options={"x-upsert": "true", "content-type": "application/pdf"})
        dados = process_pdf_simple(b_up)
        if dados:
            save_to_db(dados)
            st.success("Sincronizado!")
            st.rerun()

# --- INTERFACE: EXIBIÇÃO ---
try:
    # 1. Carrega menus do banco
    res_cat = supabase.table("hinos_categorias").select("*").order("nome_nivel1").execute()
    
    if res_cat.data:
        df_cat = pd.DataFrame(res_cat.data)
        c1, c2 = st.columns(2)
        with c1:
            escolha_n1 = st.selectbox("Categoria", df_cat['nome_nivel1'], key="cat")
            id_n1 = int(df_cat[df_cat['nome_nivel1'] == escolha_n1]['id'].iloc[0])
        
        hinos_res = supabase.table("hinos_conteudos").select("*").eq("categoria_id", id_n1).execute().data
        if hinos_res:
            hinos_ord = sorted(hinos_res, key=lambda x: int(re.search(r'\d+', x['nome_nivel2']).group()) if re.search(r'\d+', x['nome_nivel2']) else 0)
            hino_sel = st.selectbox("Hino", [h['nome_nivel2'] for h in hinos_ord], key=f"h_{id_n1}")
            
            # --- MOMENTO CRÍTICO: CARREGAMENTO DA IMAGEM ---
            # Baixamos os bytes do storage na hora
            try:
                pdf_res = supabase.storage.from_(BUCKET).download(FILE_PATH)
                
                if pdf_res and pdf_res[:4] == b'%PDF':
                    item_db = next(h for h in hinos_res if h['nome_nivel2'] == hino_sel)
                    p_num = int(item_db['texto_completo'])

                    st.divider()
                    
                    # Usamos io.BytesIO novo para cada abertura
                    with pdfplumber.open(io.BytesIO(pdf_res)) as pdf:
                        page = pdf.pages[p_num - 1]
                        lines = page.extract_text_lines()
                        y_ini, y_fim = 0, page.height

                        for l in lines:
                            if hino_sel in l['text']:
                                y_ini = l['top']
                                break
                        for l in lines:
                            if l['top'] > y_ini + 5:
                                txt = l['text'].strip()
                                if re.match(r'^\d+\.', txt) or txt.upper() in CATEGORIAS_ALVO:
                                    y_fim = l['top']
                                    break

                        # Geramos a imagem
                        img = page.crop((0, max(0, y_ini-10), page.width, y_fim)).to_image(resolution=200).original
                        
                        buf = io.BytesIO()
                        img.save(buf, format="PNG")
                        img_b64 = base64.b64encode(buf.getvalue()).decode()

                        st.markdown(f'''
                            <div style="background:white; padding:10px; border-radius:10px; border: 1px solid #ddd;">
                                <img src="data:image/png;base64,{img_b64}" style="width:100%; height:auto;">
                            </div>
                        ''', unsafe_allow_html=True)
                else:
                    st.warning("Arquivo PDF não encontrado ou incompleto no servidor.")
            except Exception as e_pdf:
                st.error(f"Erro ao processar imagem do hino: {e_pdf}")
    else:
        st.info("Nenhuma categoria encontrada.")
except Exception as e:
    st.error(f"Erro Geral: {e}")

