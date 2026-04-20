import streamlit as st
import pdfplumber
import re
from supabase import create_client
import pandas as pd
import io

# Conexão original mantida
supabase = create_client(st.secrets["URL_SUPABASE"], st.secrets["KEY_SUPABASE"])
BUCKET = "hinarios"

CATEGORIAS_LITURGICOS = [
    "ORANTES", "INICIAIS E FINAIS", "PERDÃO", "GLÓRIA", "DEUS NOS FALA", 
    "SALMO", "ACLAMAÇÃO", "OFERTÓRIO", "LOUVOR", "SANTO", "CORDEIRO", 
    "PAZ", "COMUNHÃO", "BÍBLIA", "CRUZ", "LADAINHAS – SEQUÊNCIAS - PROCLAMAÇÕES", 
    "MARIA", "PRECES"
]

def process_pdf_adaptativo(file, tipo_selecionado):
    data = []
    if "DIVERSOS" in tipo_selecionado.upper():
        current_n1 = "HINOS DIVERSOS"
        categorias_permitidas = ["HINOS DIVERSOS"]
    else:
        current_n1 = "Sem Categoria"
        categorias_permitidas = CATEGORIAS_LITURGICOS

    with pdfplumber.open(file) as pdf:
        progresso = st.progress(0)
        total_pags = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text: continue
            for line in text.split('\n'):
                t_limpo = line.strip()
                if t_limpo.upper() in categorias_permitidas:
                    current_n1 = t_limpo.upper()
                elif re.match(r'^\d+\.', t_limpo):
                    data.append({"n1": current_n1, "n2": t_limpo, "pag": i + 1})
            progresso.progress((i + 1) / total_pags)
    return data

def save_to_db(data):
    # Limpeza total para refletir o arquivo ativo
    supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
    supabase.table("hinos_categorias").delete().neq("id", 0).execute()
    
    categorias_presentes = sorted(list(set([item['n1'] for item in data])))
    for cat_nome in categorias_presentes:
        res = supabase.table("hinos_categorias").insert({"nome_nivel1": cat_nome}).execute()
        # Ajuste no acesso ao dado retornado
        if res.data:
            cat_id = res.data[0]['id']
            itens = [{"categoria_id": cat_id, "nome_nivel2": item['n2'], "texto_completo": str(item['pag'])} for item in data if item['n1'] == cat_nome]
            if itens:
                supabase.table("hinos_conteudos").insert(itens).execute()
# --- INTERFACE ---
st.set_page_config(page_title="Hinário Litúrgico", layout="wide")

st.subheader("📖 Seleção de Hinário")
doc_ativo = st.radio("Qual arquivo deseja visualizar ou atualizar?", ["HINOS LITÚRGICOS", "HINOS DIVERSOS"], horizontal=True)

NOME_STORAGE = "HINOS_LITURGICOS.pdf" if doc_ativo == "HINOS LITÚRGICOS" else "HINOS_DIVERSOS.pdf"

try:
    res_storage = supabase.storage.from_(BUCKET).download(NOME_STORAGE)
    arquivo_persistente = io.BytesIO(res_storage)
except:
    arquivo_persistente = None

with st.expander("⬆️ Gerenciar e Upload de Arquivos"):
    arquivos_carregados = st.file_uploader("Arraste seus PDFs aqui", type="pdf", accept_multiple_files=True)
    
    if arquivos_carregados:
        lista_nomes = [f.name for f in arquivos_carregados]
        arquivo_escolhido_nome = st.selectbox("Escolha qual arquivo aplicar ao rádio selecionado:", lista_nomes)
        
        if st.button(f"Sincronizar como {doc_ativo}"):
            with st.spinner("Processando..."):
                arq_obj = next(f for f in arquivos_carregados if f.name == arquivo_escolhido_nome)
                file_bytes = arq_obj.read()
                
                # Tenta remover o arquivo antes de enviar para evitar erro de duplicata (Garante o Upsert)
                try:
                    supabase.storage.from_(BUCKET).remove([NOME_STORAGE])
                except:
                    pass
                
                # Upload limpo
                supabase.storage.from_(BUCKET).upload(path=NOME_STORAGE, file=file_bytes)
                
                dados = process_pdf_adaptativo(io.BytesIO(file_bytes), doc_ativo)
                save_to_db(dados)
                st.success(f"Arquivo sincronizado como {doc_ativo}!")
                st.rerun()

try:
    res_cat = supabase.table("hinos_categorias").select("*").order("nome_nivel1").execute()
    if res_cat.data and arquivo_persistente:
        df_cat = pd.DataFrame(res_cat.data)
        c1, c2 = st.columns(2)
        with c1:
            escolha_n1 = st.selectbox("Categoria", df_cat['nome_nivel1'], key=f"cat_{doc_ativo}")
            id_n1 = int(df_cat[df_cat['nome_nivel1'] == escolha_n1]['id'].iloc[0])
        
        res_hinos = supabase.table("hinos_conteudos").select("*").eq("categoria_id", id_n1).execute().data
        if res_hinos:
            hinos_ord = sorted(res_hinos, key=lambda x: int(re.search(r'\d+', x['nome_nivel2']).group()))
            hino_sel = st.selectbox("Hino:", [h['nome_nivel2'] for h in hinos_ord], key=f"h_{escolha_n1}_{doc_ativo}")
            
            p_num = int(next(h for h in res_hinos if h['nome_nivel2'] == hino_sel)['texto_completo'])
            
            st.divider()
            with pdfplumber.open(arquivo_persistente) as pdf:
                page = pdf.pages[p_num - 1]
                text_lines = page.extract_text_lines()
                y_ini = next((l['top'] for l in text_lines if hino_sel in l['text']), 0)
                y_fim = page.height
                for l in text_lines:
                    if l['top'] > y_ini + 5:
                        txt = l['text'].strip()
                        if re.match(r'^\d+\.', txt) or txt.upper() in (CATEGORIAS_LITURGICOS + ["HINOS DIVERSOS"]):
                            y_fim = l['top']
                            break
                img = page.crop((0, max(0, y_ini - 10), page.width, y_fim)).to_image(resolution=200).original
                st.image(img, use_container_width=True)
    else:
        st.info(f"O hinário '{doc_ativo}' não possui dados sincronizados.")
except Exception as e:
    st.error(f"Erro: {e}")
