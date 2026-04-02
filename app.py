import streamlit as st
import qrcode
from io import BytesIO

# Configuração da página para o Streamlit
st.set_page_config(page_title="Gerador QR Turbo", page_icon="⚡")

st.title("🎯 Gerador de QR Code: Acesso Direto")
st.markdown("""
Se o seu celular Xiaomi mostrava apenas 'Copiar Texto', este código resolve isso 
forçando a identificação de link do sistema.
""")

# Entrada de dados
url_input = st.text_input("Digite ou cole o site aqui:", placeholder="exemplo.com").strip()

if url_input:
    # 1. TRATAMENTO DO LINK (O segredo para o Redmi)
    # Remove qualquer 'http://' que o usuário possa ter colocado para padronizar
    clean_url = url_input.replace("https://", "").replace("http://", "")
    
    # Montamos a URL final com o protocolo explícito. 
    # Dispositivos Android precisam do protocolo para ativar o 'Intent' do navegador.
    final_data = f"https://{clean_url}"

    # 2. GERAÇÃO DO QR CODE
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M, # Nível médio para melhor leitura
        box_size=15, # Quadrados maiores facilitam o foco da câmera Redmi
        border=4,
    )
    
    qr.add_data(final_data)
    qr.make(fit=True)

    # Criar a imagem com contraste alto
    img = qr.make_image(fill_color="black", back_color="white")

    # 3. CONVERSÃO PARA EXIBIÇÃO
    buf = BytesIO()
    img.save(buf, format="PNG")
    byte_im = buf.getvalue()

    # RESULTADO NA TELA
    st.success(f"Link configurado para: {final_data}")
    
    # Exibe a imagem centralizada e com tamanho bom para leitura na tela
    st.image(byte_im, caption="Aponte a câmera e clique no banner que aparecer", width=350)

    # BOTÃO DE DOWNLOAD
    st.download_button(
        label="💾 Baixar QR Code para Impressão",
        data=byte_im,
        file_name="qrcode_direto_redmi.png",
        mime="image/png"
    )

st.info("💡 **Dica para o seu Redmi Note 11:** Quando apontar a câmera, não espere abrir sozinho. Um pequeno ícone de 'globo' ou um retângulo escrito o link aparecerá no canto da tela da câmera. **Toque nele** para abrir.")
