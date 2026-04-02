import streamlit as st
import segno
from io import BytesIO

# Interface limpa
st.set_page_config(page_title="Gerador QR Turbo", page_icon="⚡")

st.title("🎯 Gerador de Link Direto (Versão Blindada)")
st.write("Esta versão força o celular a reconhecer o comando de 'Abrir Navegador'.")

# Campo de entrada
url_input = st.text_input("Cole o link do seu jogo aqui:", placeholder="seujogo.streamlit.app").strip()

if url_input:
    # 1. TRATAMENTO RIGOROSO
    # Garantimos o protocolo e removemos espaços invisíveis
    url_final = url_input if url_input.startswith(("http://", "https://")) else f"https://{url_input}"

    # 2. O SEGREDO TÉCNICO: FORMATO MECARD URL
    # Ao colocar 'URL:' na frente, o processador do seu Redmi identifica como um 'Bookmark'
    # Isso desativa a função de 'Copiar Texto' e ativa o 'Ir para o Site'
    comando_sistema = f"URL:{url_final}"

    try:
        # 3. GERAÇÃO DE BAIXÍSSIMA DENSIDADE
        # Usamos error='l' (mínimo) para que os quadrados fiquem ENORMES e fáceis de focar
        qr = segno.make_qr(comando_sistema, error='l', boost_error=False)
        
        buf = BytesIO()
        # Scale 20 e Border 10 criam o máximo contraste possível
        qr.save(buf, kind='png', scale=20, border=10)
        byte_im = buf.getvalue()

        # EXIBIÇÃO
        st.success(f"Link de sistema configurado: {url_final}")
        
        # QR Code Grande e Nítido
        st.image(byte_im, caption="APONTE A CÂMERA E CLIQUE NO ÍCONE DE GLOBO/LINK", width=450)

        st.download_button(
            label="📥 Baixar QR Code Blindado",
            data=byte_im,
            file_name="qrcode_direto_final.png",
            mime="image/png"
        )

    except Exception as e:
        st.error(f"Erro: {e}")

st.divider()
st.info("💡 **DICA FINAL:** No Redmi, o botão 'Ir para o site' muitas vezes aparece como um **pequeno ícone de QR Code ou Globo** no canto inferior direito da imagem da câmera. **Toque nele** assim que ele aparecer.")
