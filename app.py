import streamlit as st
import pdfplumber
import re
from supabase import create_client
import pandas as pd
import io

# Conexão original
supabase = create_client(st.secrets["URL_SUPABASE"], st.secrets["KEY_SUPABASE"])
BUCKET, FILE_PATH = "hinarios", "hinario_atual.pdf"

CATEGORIAS_ALVO = ["ORANTES", "INICIAIS E FINAIS", "PERDÃO", "GLÓRIA", "DEUS NOS FALA", "SALMO", "ACLAMAÇÃO", "OFERTÓRIO", "LOUVOR", "SANTO", "CORDEIRO", "PAZ", "COMUNHÃO", "BÍBLIA", "CRUZ", "LADAINHAS – SEQUÊNCIAS - PROCLAMAÇÕES", "MARIA", "PRECES"]

def process_pdf_simple(file):
    data = []
    current_n1 = "Sem Categoria"
    with pdfplumber.open(file) as pdf:
        progresso = st.progress(0)
        total_pags = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text: continue
            for line in text.split('\n'):
                t_limpo = line.strip()
                if t_limpo.upper() in CATEGORIAS_ALVO:
                    current_n1 = t_limpo.upper()
                elif re.match(r'^\d+\.', t_limpo):
                    data.append({"n1": current_n1, "n2": t_limpo, "pag": i + 1})
            progresso.progress((i + 1) / total_pags)
    return data

def save_to_db(data):
    supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
    supabase.table("hinos_categorias").delete().neq("id", 0).execute()
    for cat in CATEGORIAS_ALVO:
        res = supabase.table("hinos_categorias").insert({"nome_nivel1": cat}).execute()
        if res.data:
            cat_id = res.data[0]['id']
            itens = [{"categoria_id": cat_id, "nome_nivel2": item['n2'], "texto_completo": str(item['pag'])} for item in data if item['n1'] == cat]
            if itens: supabase.table("hinos_conteudos").insert(itens).execute()
# --- INTERFACE ---
st.set_page_config(page_title="Hinário Visual", layout="wide")

try:
    pdf_res = supabase.storage.from_(BUCKET).download(FILE_PATH)
    arquivo_persistente = io.BytesIO(pdf_res)
except: arquivo_persistente = None

with st.expander("⬆️ Upload PDF"):
    novo = st.file_uploader("Selecione o arquivo", type="pdf")
    if st.button("Atualizar Banco") and novo:
        bytes_pdf = novo.read()
        supabase.storage.from_(BUCKET).upload(path=FILE_PATH, file=bytes_pdf, file_options={"x-upsert": "true"})
        dados = process_pdf_simple(io.BytesIO(bytes_pdf))
        save_to_db(dados)
        st.success("Sincronizado!")
        st.rerun()

try:
    res_cat = supabase.table("hinos_categorias").select("*").order("nome_nivel1").execute()
    if res_cat.data and arquivo_persistente:
        df_cat = pd.DataFrame(res_cat.data)
        c1, c2 = st.columns(2)
        with c1:
            escolha_n1 = st.selectbox("Categoria", df_cat['nome_nivel1'], key="cat")
            id_n1 = int(df_cat[df_cat['nome_nivel1'] == escolha_n1]['id'].iloc[0])
        
        hinos = supabase.table("hinos_conteudos").select("*").eq("categoria_id", id_n1).execute().data
        if hinos:
            hinos_ord = sorted(hinos, key=lambda x: int(re.search(r'\d+', x['nome_nivel2']).group()))
            titulos_lista = [h['nome_nivel2'] for h in hinos_ord]
            hino_sel = st.selectbox("Hino", titulos_lista, key=f"h_{escolha_n1}")
            
            item_db = next(h for h in hinos if h['nome_nivel2'] == hino_sel)
            p_num = int(item_db['texto_completo'])

            st.divider()
            with pdfplumber.open(arquivo_persistente) as pdf:
                page = pdf.pages[p_num - 1]
                # Pegamos as linhas com as coordenadas corretas
                text_lines = page.extract_text_lines()
                
                y_ini = 0
                y_fim = page.height

                # PASSO 1: Localiza o y_ini (Início) comparando o texto selecionado
                for line in text_lines:
                    if hino_sel in line['text']:
                        y_ini = line['top']
                        break
                
                # PASSO 2: Localiza o y_fim (Fim) procurando o próximo hino ou categoria abaixo de y_ini
                for line in text_lines:
                    # Só avaliamos linhas que estão abaixo do início do hino selecionado
                    if line['top'] > y_ini + 5:
                        conteudo_linha = line['text'].strip()
                        # Se for um título de hino (começa com número)
                        if re.match(r'^\d+\.', conteudo_linha):
                            y_fim = line['top']
                            break
                        # Se for uma categoria alvo
                        if conteudo_linha.upper() in CATEGORIAS_ALVO:
                            y_fim = line['top']
                            break

                # AJUSTE FINAL: Margem de segurança e validação de altura
                y_ini_crop = max(0, y_ini - 10)
                if y_fim <= y_ini_crop: y_fim = page.height
                
                # RECORTE
                # Aumentamos para resolution=300 para o zoom não perder nitidez
                img_obj = page.crop((0, y_ini_crop, page.width, y_fim)).to_image(resolution=300).original
                
                # Convertemos a imagem em bytes para poder exibi-la via HTML
                import base64
                from io import BytesIO
                
                buffered = BytesIO()
                img_obj.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode()

                # EXIBIÇÃO COM ZOOM HABILITADO
                # Usamos um container HTML que permite o zoom nativo do navegador
                st.markdown(
                    f"""
                    <div style="width: 100%; overflow: auto;">
                        <img src="data:image/png;base64,{img_base64}" 
                             style="width: 100%; height: auto; cursor: zoom-in;" 
                             onclick="window.open(this.src, '_blank');"
                             title="Clique para abrir em tela cheia e dar zoom">
                    </div>
                    <p style="text-align: center; color: gray; font-size: 0.8rem;">
                        Se estiver no celular pressione o hino e compartilhe para usar o zoom.
                    </p>
                    """, 
                    unsafe_allow_html=True
                )

    else:
        st.info("Aguardando PDF...")
except Exception as e:
    st.error(f"Erro ao carregar: {e}")
