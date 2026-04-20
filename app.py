import streamlit as st
import pdfplumber
import re
from supabase import create_client
import pandas as pd
import io

# Conexão original
supabase = create_client(st.secrets["URL_SUPABASE"], st.secrets["KEY_SUPABASE"])
BUCKET, FILE_PATH = "hinarios", "hinario_atual.pdf"

# Lista que engloba as categorias de ambos os arquivos
CATEGORIAS_ALVO = [
    "ORANTES", "INICIAIS E FINAIS", "PERDÃO", "GLÓRIA", "DEUS NOS FALA", 
    "SALMO", "ACLAMAÇÃO", "OFERTÓRIO", "LOUVOR", "SANTO", "CORDEIRO", 
    "PAZ", "COMUNHÃO", "BÍBLIA", "CRUZ", "LADAINHAS – SEQUÊNCIAS - PROCLAMAÇÕES", 
    "MARIA", "PRECES", "HINOS DIVERSOS"
]

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
                # Identifica Nível 1 (Categorias Alvo + Hinos Diversos)
                if t_limpo.upper() in CATEGORIAS_ALVO:
                    current_n1 = t_limpo.upper()
                # Identifica Nível 2 (Hinos Numerados)
                elif re.match(r'^\d+\.', t_limpo):
                    data.append({"n1": current_n1, "n2": t_limpo, "pag": i + 1})
            progresso.progress((i + 1) / total_pags)
    return data

def save_to_db(data):
    # Lógica original de deleção para resetar o banco
    supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
    supabase.table("hinos_categorias").delete().neq("id", 0).execute()
    
    # Registra apenas as categorias que existem no PDF processado
    categorias_presentes = sorted(list(set([item['n1'] for item in data])))
    for cat_nome in categorias_presentes:
        res = supabase.table("hinos_categorias").insert({"nome_nivel1": cat_nome}).execute()
        if res.data:
            cat_id = res.data[0]['id']
            itens = [{"categoria_id": cat_id, "nome_nivel2": item['n2'], "texto_completo": str(item['pag'])} for item in data if item['n1'] == cat_nome]
            if itens:
                supabase.table("hinos_conteudos").insert(itens).execute()
# --- INTERFACE ---
st.set_page_config(page_title="Hinário Litúrgico", layout="wide")

# Tenta carregar o PDF persistente do Storage
try:
    pdf_res = supabase.storage.from_(BUCKET).download(FILE_PATH)
    arquivo_persistente = io.BytesIO(pdf_res)
except:
    arquivo_persistente = None

with st.expander("⬆️ Configurações de Upload"):
    arquivos_novos = st.file_uploader("Selecione os arquivos PDF", type="pdf", accept_multiple_files=True)
    if arquivos_novos:
        nomes = [f.name for f in arquivos_novos]
        escolhido = st.selectbox("Qual arquivo deseja ativar no sistema?", nomes)
        arq_obj = next(f for f in arquivos_novos if f.name == escolhido)
        
        if st.button("Atualizar Banco e App com Selecionado"):
            with st.spinner(f"Processando {escolhido}..."):
                file_bytes = arq_obj.read()
                # Salva no Storage sobrescrevendo o anterior
                supabase.storage.from_(BUCKET).upload(path=FILE_PATH, file=file_bytes, file_options={"x-upsert": "true"})
                # Processa e salva no banco
                dados = process_pdf_simple(io.BytesIO(file_bytes))
                save_to_db(dados)
                st.success(f"Arquivo '{escolhido}' agora é o oficial!")
                st.rerun()

try:
    res_cat = supabase.table("hinos_categorias").select("*").order("nome_nivel1").execute()
    if res_cat.data and arquivo_persistente:
        df_cat = pd.DataFrame(res_cat.data)
        c1, c2 = st.columns(2)
        with c1:
            escolha_n1 = st.selectbox("Categoria", df_cat['nome_nivel1'], key="cat_sel")
            id_n1 = int(df_cat[df_cat['nome_nivel1'] == escolha_n1]['id'].iloc[0])
        
        hinos = supabase.table("hinos_conteudos").select("*").eq("categoria_id", id_n1).execute().data
        if hinos:
            # Ordenação numérica original
            hinos_ord = sorted(hinos, key=lambda x: int(re.search(r'\d+', x['nome_nivel2']).group()))
            titulos = [h['nome_nivel2'] for h in hinos_ord]
            hino_sel = st.selectbox("Hino", titulos, key=f"h_{escolha_n1}")
            
            # Lógica de Crop baseada na sua sugestão de Início e Fim
            idx_atual = titulos.index(hino_sel)
            proximo_t = titulos[idx_atual + 1] if idx_atual + 1 < len(titulos) else None
            p_num = int(next(h for h in hinos if h['nome_nivel2'] == hino_sel)['texto_completo'])

            st.divider()
            with pdfplumber.open(arquivo_persistente) as pdf:
                page = pdf.pages[p_num - 1]
                text_lines = page.extract_text_lines()
                
                # Início: Posição do título selecionado
                y_ini = next((l['top'] for l in text_lines if hino_sel in l['text']), 0)
                # Fim: Próximo título ou Categoria ou fim da página
                y_fim = page.height
                for l in text_lines:
                    if l['top'] > y_ini + 5:
                        if re.match(r'^\d+\.', l['text'].strip()) or l['text'].strip().upper() in CATEGORIAS_ALVO:
                            y_fim = l['top']
                            break
                
                # Crop e Exibição
                img = page.crop((0, max(0, y_ini - 10), page.width, y_fim)).to_image(resolution=200).original
                st.image(img, use_container_width=True)
    else:
        st.info("Aguardando upload de um PDF para exibição.")
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
