import streamlit as st
import pdfplumber
import re
from supabase import create_client
import pandas as pd
import io
import base64
import requests

# --- CONFIGURAÇÃO E CONEXÃO ---
st.set_page_config(page_title="Hinário Visual", layout="wide")

# Inicializa conexão com Supabase
try:
    supabase = create_client(st.secrets["URL_SUPABASE"], st.secrets["KEY_SUPABASE"])
except Exception as e:
    st.error(f"Erro crítico de conexão: {e}")
    st.stop()

BUCKET = "hinarios"
FILE_PATH = "hinario_atual.pdf"
CATEGORIAS_ALVO = [
    "ORANTES", "INICIAIS E FINAIS", "PERDÃO", "GLÓRIA", "DEUS NOS FALA", 
    "SALMO", "ACLAMAÇÃO", "OFERTÓRIO", "LOUVOR", "SANTO", "CORDEIRO", 
    "PAZ", "COMUNHÃO", "BÍBLIA", "CRUZ", "LADAINHAS – SEQUÊNCIAS - PROCLAMAÇÕES", 
    "MARIA", "HINOS DIVERSOS", "PRECES"
]

# --- FUNÇÕES DE SUPORTE ---

@st.cache_data(show_spinner="Baixando Hinário do Servidor...", ttl=3600)
def download_pdf_robusto():
    """Baixa o PDF usando URL pública e requests (melhor para arquivos grandes)"""
    try:
        url = supabase.storage.from_(BUCKET).get_public_url(FILE_PATH)
        response = requests.get(url, timeout=120) # 2 minutos de limite
        if response.status_code == 200 and response.content[:4] == b'%PDF':
            return response.content
        return None
    except Exception as e:
        return None

def process_pdf_simple(file_bytes):
    data = []
    current_n1 = "Sem Categoria"
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            progresso = st.progress(0)
            total_pags = len(pdf.pages)
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if not text: continue
                for line in text.split('\n'):
                    t_limpo = line.strip()
                    if t_limpo.upper() in CATEGORIAS_ALVO:
                        current_n1 = t_limpo.upper()
                    elif re.match(r'^\d+\.', t_limpo) and t_limpo == t_limpo.upper():
                        data.append({"n1": current_n1, "n2": t_limpo, "pag": i + 1})
                progresso.progress((i + 1) / total_pags)
        return data
    except Exception as e:
        st.error(f"Erro ao processar estrutura do PDF: {e}")
        return []

def save_to_db(data):
    # Limpa dados antigos
    supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
    supabase.table("hinos_categorias").delete().neq("id", 0).execute()
    
    for cat in CATEGORIAS_ALVO:
        res = supabase.table("hinos_categorias").insert({"nome_nivel1": cat}).execute()
        if res.data:
            cat_id = res.data[0]['id']
            itens = [
                {
                    "categoria_id": cat_id, 
                    "nome_nivel2": item['n2'], 
                    "texto_completo": str(item['pag'])
                } for item in data if item['n1'] == cat
            ]
            if itens: 
                supabase.table("hinos_conteudos").insert(itens).execute()

# --- LOGICA DE CARREGAMENTO ---
# Tentamos baixar o arquivo usando a função com cache
pdf_bytes = download_pdf_robusto()
arquivo_persistente = io.BytesIO(pdf_bytes) if pdf_bytes else None

# --- INTERFACE: UPLOAD ---
with st.expander("⬆️ Upload PDF"):
    novo = st.file_uploader("Selecione o arquivo (Substitui o atual)", type="pdf")
    if st.button("Atualizar Banco e Arquivo") and novo:
        with st.spinner("Limpando versões anteriores e processando novo arquivo..."):
            bytes_upload = novo.read()
            
            # 1. Limpa o Bucket
            try:
                lista = supabase.storage.from_(BUCKET).list()
                if lista:
                    nomes = [f['name'] for f in lista]
                    supabase.storage.from_(BUCKET).remove(nomes)
            except: pass
            
            # 2. Upload
            supabase.storage.from_(BUCKET).upload(
                path=FILE_PATH, 
                file=bytes_upload, 
                file_options={"x-upsert": "true", "content-type": "application/pdf"}
            )
            
            # 3. Processa e Salva
            dados = process_pdf_simple(bytes_upload)
            if dados:
                save_to_db(dados)
                st.cache_data.clear() # Limpa o cache para baixar o novo arquivo
                st.success("Sincronizado! Reiniciando...")
                st.rerun()

# --- INTERFACE: EXIBIÇÃO ---
try:
    res_cat = supabase.table("hinos_categorias").select("*").order("nome_nivel1").execute()
    
    if res_cat.data and arquivo_persistente:
        df_cat = pd.DataFrame(res_cat.data)
        c1, c2 = st.columns(2)
        with c1:
            escolha_n1 = st.selectbox("Categoria", df_cat['nome_nivel1'], key="cat")
            id_n1 = int(df_cat[df_cat['nome_nivel1'] == escolha_n1]['id'].iloc[0])
        
        hinos_data = supabase.table("hinos_conteudos").select("*").eq("categoria_id", id_n1).execute().data
        if hinos_data:
            # Ordenação numérica
            hinos_ord = sorted(hinos_data, key=lambda x: int(re.search(r'\d+', x['nome_nivel2']).group()) if re.search(r'\d+', x['nome_nivel2']) else 0)
            titulos_lista = [h['nome_nivel2'] for h in hinos_ord]
            hino_sel = st.selectbox("Hino", titulos_lista, key=f"h_{escolha_n1}")
            
            item_db = next(h for h in hinos_data if h['nome_nivel2'] == hino_sel)
            p_num = int(item_db['texto_completo'])

            st.divider()
            
            # Processamento visual
            with pdfplumber.open(arquivo_persistente) as pdf:
                page = pdf.pages[p_num - 1]
                text_lines = page.extract_text_lines()
                y_ini, y_fim = 0, page.height

                for line in text_lines:
                    if hino_sel in line['text']:
                        y_ini = line['top']
                        break
                for line in text_lines:
                    if line['top'] > y_ini + 5:
                        conteudo = line['text'].strip()
                        if re.match(r'^\d+\.', conteudo) or conteudo.upper() in CATEGORIAS_ALVO:
                            y_fim = line['top']
                            break

                y_ini_crop = max(0, y_ini - 10)
                if y_fim <= y_ini_crop: y_fim = page.height
                
                # Resolução 150 para economizar RAM no Streamlit Cloud
                img_obj = page.crop((0, y_ini_crop, page.width, y_fim)).to_image(resolution=150).original
                
                buffered = io.BytesIO()
                img_obj.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode()

                st.markdown(
                    f"""
                    <div style="width: 100%; background-color: white; border-radius: 8px; padding: 5px;">
                        <img src="data:image/png;base64,{img_base64}" style="width: 100%; height: auto;">
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
    else:
        st.info("Aguardando PDF ou configuração inicial...")
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
