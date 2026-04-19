import streamlit as st
from pdfplumber import open as open_pdf
from supabase import create_client
import pandas as pd
import re

# Conexão original mantida
supabase = create_client(st.secrets["URL_SUPABASE"], st.secrets["KEY_SUPABASE"])

# Lista exata definida por você para garantir o Nível 1
CATEGORIAS_ALVO = [
    "ORANTES", "INICIAIS E FINAIS", "PERDÃO", "GLÓRIA", "DEUS NOS FALA", 
    "SALMO", "ACLAMAÇÃO", "OFERTÓRIO", "LOUVOR", "SANTO", "CORDEIRO", 
    "PAZ", "COMUNHÃO", "BÍBLIA", "CRUZ", "LADAINHAS – SEQUÊNCIAS - PROCLAMAÇÕES", 
    "MARIA", "PRECES"
]

def process_pdf(file):
    data = []
    current_n1 = "Sem Categoria"
    current_n2 = None
    current_text = []

    with open_pdf(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            
            linhas = text.split('\n')
            for linha in linhas:
                texto = linha.strip()
                
                if not texto or "Sumário" in texto: 
                    continue

                # Identifica Nível 1 (Baseado na sua lista e em Caixa Alta)
                if texto.upper() in CATEGORIAS_ALVO:
                    if current_n2:
                        data.append({"n1": current_n1, "n2": current_n2, "texto": "\n".join(current_text)})
                    
                    current_n1 = texto.upper()
                    current_n2 = None 
                    current_text = []
                    # Garante que a categoria seja registrada mesmo que não tenha hinos imediatos
                    data.append({"n1": current_n1, "n2": None, "texto": ""})
                    continue

                # Identifica Nível 2 (Começa com número e ponto + Título em Caixa Alta)
                # Exemplo: "1. VENHA A NÓS O TEU REINO"
                is_n2 = re.match(r'^\d+\.', texto) and any(c.isupper() for c in texto)
                
                if is_n2:
                    if current_n2:
                        data.append({"n1": current_n1, "n2": current_n2, "texto": "\n".join(current_text)})
                    
                    # Remove resquícios de sumário (ex: "......... 10")
                    current_n2 = re.sub(r'\s\.+\s\d+$', '', texto)
                    current_text = []
                    
                # Captura o texto normal (Corpo do texto / Acordes)
                else:
                    if current_n2:
                        # Ignora números de página isolados que sobram no PDF
                        if not texto.isdigit():
                            current_text.append(texto)

    # Salva o último hino do arquivo
    if current_n2:
        data.append({"n1": current_n1, "n2": current_n2, "texto": "\n".join(current_text)})
        
    return data
def save_to_db(data):
    # Lógica original de deleção para resetar o banco
    supabase.table("hinos_conteudos").delete().neq("id", 0).execute()
    supabase.table("hinos_categorias").delete().neq("id", 0).execute()
    
    # Puxa apenas as categorias que realmente foram encontradas no documento
    categorias_encontradas = sorted(list(set([item['n1'] for item in data])))
    
    for cat_nome in categorias_encontradas:
        # Inserção de Categoria
        res = supabase.table("hinos_categorias").insert({"nome_nivel1": cat_nome}).execute()
        cat_id = res.data[0]['id']
        
        # Filtra os hinos (N2) pertencentes a esta categoria
        itens = [
            {"categoria_id": cat_id, "nome_nivel2": item['n2'], "texto_completo": item['texto']} 
            for item in data if item['n1'] == cat_nome and item['n2'] is not None
        ]
        
        # Inserção em lote para evitar lentidão
        if itens:
            supabase.table("hinos_conteudos").insert(itens).execute()

# --- INTERFACE ORIGINAL ---
st.set_page_config(page_title="Hinário Litúrgico", layout="wide")

with st.expander("⬆️ Configurações de Upload (PDF)"):
    arquivo = st.file_uploader("Upload do arquivo PDF", type="pdf")
    if st.button("Atualizar Banco de Dados") and arquivo:
        with st.spinner("Processando..."):
            dados = process_pdf(arquivo)
            save_to_db(dados)
            st.success(f"Sucesso! {len([d for d in dados if d['n2']])} hinos carregados.")
            st.rerun()

# --- EXIBIÇÃO ORIGINAL ---
try:
    res_cat = supabase.table("hinos_categorias").select("*").order("nome_nivel1").execute()
    if res_cat.data:
        df_cat = pd.DataFrame(res_cat.data)
        
        c1, c2 = st.columns(2)
        with c1:
            escolha_n1 = st.selectbox("Selecione a Categoria", df_cat['nome_nivel1'])
            id_n1 = int(df_cat[df_cat['nome_nivel1'] == escolha_n1]['id'].iloc[0])
        
        with c2:
            termo = st.text_input("🔍 Buscar hino por nome")

        query = supabase.table("hinos_conteudos").select("*").eq("categoria_id", id_n1)
        if termo:
            query = query.ilike("nome_nivel2", f"%{termo}%")
        
        hinos = query.execute().data

        if hinos:
            titulos_hinos = [h['nome_nivel2'] for h in hinos]
            hino_selecionado_nome = st.radio("Escolha o hino para ler:", titulos_hinos)
            
            conteudo_hino = next(h for h in hinos if h['nome_nivel2'] == hino_selecionado_nome)
            
            st.markdown("---")
            st.subheader(conteudo_hino['nome_nivel2'])
            # Usamos st.text para manter a formatação original de acordes/versos
            st.text(conteudo_hino['texto_completo'])
        else:
            st.warning("Nenhum hino encontrado nesta categoria.")
except Exception as e:
    st.info("Aguardando upload do primeiro arquivo...")
