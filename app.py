import streamlit as st
import pdfplumber
import re
from supabase import create_client
import pandas as pd
import io
import base64

# --- CONFIGURAÇÃO E CONEXÃO ---
st.set_page_config(page_title="Hinário Visual", layout="wide")

# Inicializa conexão
try:
    supabase = create_client(st.secrets["URL_SUPABASE"], st.secrets["KEY_SUPABASE"])
except Exception as e:
    st.error(f"Erro na conexão com Supabase: {e}")
    st.stop()

BUCKET, FILE_PATH = "hinarios", "hinario_atual.pdf"
CATEGORIAS_ALVO = ["ORANTES", "INICIAIS E FINAIS", "PERDÃO", "GLÓRIA", "DEUS NOS FALA", "SALMO", "ACLAMAÇÃO", "OFERTÓRIO", "LOUVOR", "SANTO", "CORDEIRO", "PAZ", "COMUNHÃO", "BÍBLIA", "CRUZ", "LADAINHAS – SEQUÊNCIAS - PROCLAMAÇÕES", "MARIA", "HINOS DIVERSOS", "PRECES"]

def process_pdf_simple(file):
    data = []
    current_n1 = "Sem Categoria"
    # Abre o arquivo com tratamento de erro
    try:
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
                    elif re.match(r'^\d+\.', t_limpo) and t_limpo == t_limpo.upper():
                        data.append({"n1": current_n1, "n2": t_limpo, "pag": i + 1})
                progresso.progress((i + 1) / total_pags)
        return data
    except Exception as e:
        st.error(f"Erro ao ler estrutura do PDF: {e}")
        return []

def save_to_db(data):
    # Limpa dados antigos das tabelas
    supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
    supabase.table("hinos_categorias").delete().neq("id", 0).execute()
    
    for cat in CATEGORIAS_ALVO:
        res = supabase.table("hinos_categorias").insert({"nome_nivel1": cat}).execute()
        if res.data:
            cat_id = res.data[0]['id']
            itens = [{"categoria_id": cat_id, "nome_nivel2": item['n2'], "texto_completo": str(item['pag'])} for item in data if item['n1'] == cat]
            if itens: 
                supabase.table("hinos_conteudos").insert(itens).execute()

# --- LÓGICA DE DOWNLOAD ---
arquivo_persistente = None
try:
    # Baixa o PDF do storage
    pdf_res = supabase.storage.from_(BUCKET).download(FILE_PATH)
    # Valida se é um PDF real (checa assinatura do arquivo %PDF)
    if pdf_res and pdf_res[:4] == b'%PDF':
        arquivo_persistente = io.BytesIO(pdf_res)
        arquivo_persistente.seek(0)
    else:
        arquivo_persistente = None
except:
    arquivo_persistente = None

# --- INTERFACE: UPLOAD ---
with st.expander("⬆️ Upload PDF (Substitui Atual)"):
    novo = st.file_uploader("Selecione o arquivo PDF", type="pdf")
    if st.button("Atualizar Banco e Arquivo") and novo:
        with st.spinner("Processando..."):
            bytes_pdf = novo.read()
            
            # 1. Deleta arquivos antigos no Storage para evitar duplicidade
            try:
                lista_arquivos = supabase.storage.from_(BUCKET).list()
                nomes = [f['name'] for f in lista_arquivos]
                if nomes:
                    supabase.storage.from_(BUCKET).remove(nomes)
            except: pass # Se falhar a lista, tenta o upload direto
            
            # 2. Upload do novo arquivo
            supabase.storage.from_(BUCKET).upload(path=FILE_PATH, file=bytes_pdf, file_options={"x-upsert": "true", "content-type": "application/pdf"})
            
            # 3. Processa e Salva no Banco
            dados = process_pdf_simple(io.BytesIO(bytes_pdf))
            if dados:
                save_to_db(dados)
                st.success("Tudo atualizado! O app irá reiniciar.")
                st.rerun()
            else:
                st.error("Falha ao processar o PDF. Verifique se ele contém texto extraível.")

# --- INTERFACE: EXIBIÇÃO ---
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
            # Ordenação numérica inteligente
            hinos_ord = sorted(hinos, key=lambda x: int(re.search(r'\d+', x['nome_nivel2']).group()) if re.search(r'\d+', x['nome_nivel2']) else 0)
            titulos_lista = [h['nome_nivel2'] for h in hinos_ord]
            hino_sel = st.selectbox("Hino", titulos_lista, key=f"h_{escolha_n1}")
            
            item_db = next(h for h in hinos if h['nome_nivel2'] == hino_sel)
            p_num = int(item_db['texto_completo'])

            st.divider()
            
            # Extração da imagem da página
            with pdfplumber.open(arquivo_persistente) as pdf:
                page = pdf.pages[p_num - 1]
                text_lines = page.extract_text_lines()
                
                y_ini = 0
                y_fim = page.height

                for line in text_lines:
                    if hino_sel in line['text']:
                        y_ini = line['top']
                        break
                
                for line in text_lines:
                    if line['top'] > y_ini + 5:
                        conteudo_linha = line['text'].strip()
                        if re.match(r'^\d+\.', conteudo_linha) or conteudo_linha.upper() in CATEGORIAS_ALVO:
                            y_fim = line['top']
                            break

                y_ini_crop = max(0, y_ini - 10)
                if y_fim <= y_ini_crop: y_fim = page.height
                
                img_obj = page.crop((0, y_ini_crop, page.width, y_fim)).to_image(resolution=200).original
                
                buffered = io.BytesIO()
                img_obj.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode()

                st.markdown(
                    f"""
                    <div style="width: 100%; overflow: auto; background-color: white; padding: 10px; border-radius: 10px;">
                        <img src="data:image/png;base64,{img_base64}" 
                             style="width: 100%; height: auto; cursor: zoom-in;" 
                             onclick="window.open(this.src, '_blank');">
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
    else:
        if not arquivo_persistente:
            st.info("Aguardando arquivo PDF ser carregado no Storage...")
        else:
            st.info("Nenhum hino encontrado no banco de dados.")
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
