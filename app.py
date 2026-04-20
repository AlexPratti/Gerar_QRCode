import streamlit as st
import pdfplumber
import re
from supabase import create_client
import pandas as pd
import io

# Conexão original mantida
supabase = create_client(st.secrets["URL_SUPABASE"], st.secrets["KEY_SUPABASE"])

# Configurações de persistência no Storage
BUCKET = "hinarios"
FILE_PATH = "hinario_atual.pdf"

CATEGORIAS_ALVO = [
    "ORANTES", "INICIAIS E FINAIS", "PERDÃO", "GLÓRIA", "DEUS NOS FALA", 
    "SALMO", "ACLAMAÇÃO", "OFERTÓRIO", "LOUVOR", "SANTO", "CORDEIRO", 
    "PAZ", "COMUNHÃO", "BÍBLIA", "CRUZ", "LADAINHAS – SEQUÊNCIAS - PROCLAMAÇÕES", 
    "MARIA", "PRECES"
]

def process_pdf_with_crop_coords(file):
    data = []
    current_n1 = "Sem Categoria"
    
    with pdfplumber.open(file) as pdf:
        progresso = st.progress(0)
        total_paginas = len(pdf.pages)
        
        for i, page in enumerate(pdf.pages):
            words = page.extract_words()
            text_lines = page.extract_text().split('\n')
            
            for line in text_lines:
                texto_limpo = line.strip()
                if not texto_limpo: continue
                
                # Identifica Nível 1
                if texto_limpo.upper() in CATEGORIAS_ALVO:
                    current_n1 = texto_limpo.upper()
                    continue

                # Identifica Nível 2 (Número + Ponto)
                if re.match(r'^\d+\.', texto_limpo):
                    num_tit = texto_limpo.split()[0]
                    # Localiza o Y exato do título para o CROP
                    y_top = 0
                    for w in words:
                        if w == num_tit:
                            y_top = float(w['top'])
                            break
                    
                    # Se já havia um hino anterior na mesma página, o fim dele é o início deste
                    if data and data[-1]['pag_fim'] == i + 1:
                        data[-1]['y_fim'] = y_top - 5
                    
                    data.append({
                        "n1": current_n1,
                        "n2": texto_limpo,
                        "pag_inicio": i + 1,
                        "y_ini": y_top - 10 if y_top > 10 else 0,
                        "pag_fim": i + 1,
                        "y_fim": float(page.height) 
                    })
            progresso.progress((i + 1) / total_paginas)
            
    return data

def get_persistent_pdf():
    try:
        # Baixa o arquivo do Storage para que ele permaneça no app
        res = supabase.storage.from_(BUCKET).download(FILE_PATH)
        return io.BytesIO(res)
    except:
        return None
def save_to_db(data):
    # Lógica original de deleção
    supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
    supabase.table("hinos_categorias").delete().neq("id", 0).execute()
    
    for cat_nome in CATEGORIAS_ALVO:
        res = supabase.table("hinos_categorias").insert({"nome_nivel1": cat_nome}).execute()
        if res.data:
            # Pega o ID (Supabase retorna lista)
            cat_id = res.data[0]['id']
            
            # Salvamos as coordenadas de recorte no campo texto_completo
            itens = [
                {
                    "categoria_id": cat_id, 
                    "nome_nivel2": item['n2'], 
                    "texto_completo": f"{item['pag_inicio']};{item['y_ini']};{item['y_fim']}" 
                } 
                for item in data if item['n1'] == cat_nome
            ]
            if itens:
                supabase.table("hinos_conteudos").insert(itens).execute()

# --- INTERFACE (Preservando sua estrutura original) ---
st.set_page_config(page_title="Hinário Visual", layout="wide")

# Carregamento automático do PDF do Storage
arquivo_persistente = get_persistent_pdf()

with st.expander("⬆️ Upload PDF"):
    arquivo_novo = st.file_uploader("Selecione o arquivo", type="pdf")
    if st.button("Atualizar Banco") and arquivo_novo:
        with st.spinner("Salvando PDF e sincronizando dados..."):
            file_bytes = arquivo_novo.read()
            # Salva no Storage sobrescrevendo o anterior
            supabase.storage.from_(BUCKET).upload(
                path=FILE_PATH,
                file=file_bytes,
                file_options={"x-upsert": "true"}
            )
            # Processa as coordenadas
            dados = process_pdf_with_crop_coords(io.BytesIO(file_bytes))
            save_to_db(dados)
            st.success("Sincronizado!")
            st.rerun()

try:
    res_cat = supabase.table("hinos_categorias").select("*").order("nome_nivel1").execute()
    if res_cat.data and arquivo_persistente:
        df_cat = pd.DataFrame(res_cat.data)
        c1, c2 = st.columns(2)
        
        with c1:
            escolha_n1 = st.selectbox("Categoria", df_cat['nome_nivel1'], key="cat_principal")
            id_n1 = int(df_cat[df_cat['nome_nivel1'] == escolha_n1]['id'].iloc[0])
        
        # Busca hinos da categoria selecionada
        hinos = supabase.table("hinos_conteudos").select("*").eq("categoria_id", id_n1).execute().data

        if hinos:
            # Ordenação numérica correta
            hinos_ord = sorted(hinos, key=lambda x: int(re.search(r'\d+', x['nome_nivel2']).group()))
            # Key dinâmica resolve o hino que "sobra" da lista anterior
            hino_sel = st.selectbox("Hino:", [h['nome_nivel2'] for h in hinos_ord], key=f"h_{escolha_n1}")
            
            dados_hino = next(h for h in hinos if h['nome_nivel2'] == hino_sel)
            
            # Recupera Coordenadas: pagina;y_inicio;y_fim
            c = dados_hino['texto_completo'].split(';')
            p_num, y_ini, y_fim = int(c[0]), float(c[1]), float(c[2])
            
            st.divider()
            with pdfplumber.open(arquivo_persistente) as pdf:
                page = pdf.pages[p_num - 1]
                # Trava de segurança para o recorte
                if y_fim <= y_ini: y_fim = float(page.height)
                
                # RECORTE: Isola o hino selecionado removendo os anteriores/posteriores
                recorte = page.crop((0, y_ini, page.width, y_fim))
                img = recorte.to_image(resolution=200).original
                st.image(img, use_container_width=True)
    else:
        if not arquivo_persistente:
            st.info("Aguardando upload do primeiro PDF...")
        else:
            st.info("Banco de dados vazio ou carregando...")
except Exception as e:
    st.error(f"Erro: {e}")
