import streamlit as st
import google.generativeai as genai
import sqlite3
from datetime import datetime
import io
import os  # Importar el módulo os

# --- Configuración de la API ---
API_KEY = st.secrets.get("API_KEY")
if not API_KEY:
    st.error("No se encontró la clave de la API. Asegúrate de haberla configurado en Streamlit Cloud.")
    st.stop()
genai.configure(api_key=API_KEY)

# --- Obtener modelos disponibles y filtrar ---
available_models = genai.list_models()
model_options = [
    m.name for m in available_models
    if 'generateContent' in m.supported_generation_methods
    and 'deprecated' not in m.name.lower()
    and not m.name.lower().endswith('-latest')
    and m.name not in ['gemini-pro-vision'] #Excluir gemini-pro-vision por que no funciona en chat
]

if 'selected_model' not in st.session_state:
    if 'gemini-pro' in model_options:
        st.session_state['selected_model'] = 'gemini-pro'
    elif model_options:
        st.session_state['selected_model'] = model_options[0]
    else:
        st.error("No se encontró ningún modelo válido para la API")
        st.stop()

try:
    selected_model_name = st.selectbox("Selecciona un modelo:", model_options, index=model_options.index(st.session_state['selected_model']))
    st.session_state['selected_model'] = selected_model_name
except Exception as e:
    st.error(f"Ocurrió un error al seleccionar el modelo: {e}. Seleccionando modelo por defecto: {model_options[0]}")
    selected_model_name = model_options[0]
    st.session_state['selected_model'] = selected_model_name

model = genai.GenerativeModel(selected_model_name)

# Modelo para código
code_model_name = None
for m in available_models:
    if 'code' in m.name.lower() and 'generateContent' in m.supported_generation_methods and 'deprecated' not in m.name.lower():
        code_model_name = m.name
        break

if code_model_name:
    code_model = genai.GenerativeModel(code_model_name)
    print(f"Usando modelo para código: {code_model_name}")
else:
    code_model = model
    print("No se encontró un modelo específico para código, usando el modelo por defecto")

# --- Clase Chat ---
class Chat:
    def __init__(self, db_path="chat_history.db"):
        self.db_path = db_path
        self._create_main_table()
        self._initialize_chat()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _create_main_table(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""CREATE TABLE IF NOT EXISTS chats (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    name TEXT UNIQUE,
                                    date TEXT
                                )""")
            conn.commit()
        except sqlite3.Error as e:
            st.error(f"Error al crear la tabla 'chats': {e}")
            conn.rollback()
        finally:
            conn.close()

    def _initialize_chat(self):
      conn = self._get_connection()
      cursor = conn.cursor()
      try:
        cursor.execute("SELECT id, name FROM chats ORDER BY id DESC LIMIT 1")
        last_chat = cursor.fetchone()
        if last_chat:
            st.session_state['selected_chat_id'] = last_chat[0]
            st.session_state['selected_chat_name'] = last_chat[1]
            self._add_chat_table(st.session_state['selected_chat_id']) #Crea tabla si ya existe chat
        else:
          st.session_state['selected_chat_id'] = 1
          st.session_state['selected_chat_name'] = "Chat 1"
          self._add_chat_table(st.session_state['selected_chat_id']) #Crea la tabla para el chat inicial
      except sqlite3.Error as e:
          st.error(f"Error al inicializar el chat: {e}")
          st.session_state['selected_chat_id'] = 1
          st.session_state['selected_chat_name'] = "Chat 1"
          self._add_chat_table(st.session_state['selected_chat_id']) #Crea la tabla para el chat inicial
      finally:
        conn.close()

    def _add_chat_table(self, chat_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"""CREATE TABLE IF NOT EXISTS chat_{chat_id} (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    date TEXT,
                                    speaker TEXT,
                                    message TEXT,
                                    file_data BLOB,  -- Para almacenar datos del archivo
                                    file_name TEXT   -- Para almacenar el nombre del archivo
                                    )""")
            conn.commit()
        except sqlite3.Error as e:
            st.error(f"Error al crear la tabla del chat {chat_id}: {e}")
            conn.rollback()
        finally:
            conn.close()

    def add_message(self, speaker, message, file_data=None, file_name=None):
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cursor.execute(f"INSERT INTO chat_{st.session_state['selected_chat_id']} (date, speaker, message, file_data, file_name) VALUES (?, ?, ?, ?, ?)", (now, speaker, message, file_data, file_name))
            conn.commit()
        except sqlite3.Error as e:
            st.error(f"Error al añadir el mensaje: {e}")
            conn.rollback()
        finally:
            conn.close()

    def get_all_chats(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT name, id FROM chats")
            chats = cursor.fetchall()
            return chats
        except sqlite3.Error as e:
            st.error(f"Error al obtener chats: {e}")
            return []
        finally:
            conn.close()

    def get_history(self):
      if not st.session_state.get('selected_chat_id'):
          return []
      conn = self._get_connection()
      cursor = conn.cursor()
      try:
          cursor.execute(f"SELECT speaker, message, file_data, file_name FROM chat_{st.session_state['selected_chat_id']}")
          history = cursor.fetchall()
          return history
      except sqlite3.Error as e:
          st.error(f"Error al obtener el historial del chat: {e}")
          return []
      finally:
          conn.close()

    def add_chat(self, name):
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cursor.execute("INSERT INTO chats (name, date) VALUES (?, ?)", (name, now))
            conn.commit()
            chat_id = cursor.lastrowid
            st.session_state['selected_chat_id'] = chat_id
            st.session_state['selected_chat_name'] = name
            self._add_chat_table(chat_id)
        except sqlite3.Error as e:
            st.error(f"Error al añadir un nuevo chat: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def create_chat_with_first_message(self, first_message):
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cursor.execute("INSERT INTO chats (name, date) VALUES (?, ?)", (first_message[:50] , now)) #Guardar el nombre del chat con la primera pregunta
            conn.commit()
            chat_id = cursor.lastrowid
            st.session_state['selected_chat_id'] = chat_id
            st.session_state['selected_chat_name'] = first_message[:50]  # Usa la primera pregunta como nombre del chat
            self._add_chat_table(chat_id)
        except sqlite3.Error as e:
            st.error(f"Error al añadir un nuevo chat: {e}")
            conn.rollback()
        finally:
            conn.close()

    def delete_chat(self, id):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"DROP TABLE IF EXISTS chat_{id}")
            cursor.execute("DELETE FROM chats WHERE id=?", (id,))
            conn.commit()
            st.session_state['selected_chat_id'] = None
            st.session_state['selected_chat_name'] = None
        except sqlite3.Error as e:
            st.error(f"Error al eliminar el chat: {e}")
            conn.rollback()
        finally:
            conn.close()


# --- Función para generar respuesta ---
def generate_response(prompt, chat_history, uploaded_file=None):
    try:
        full_prompt = ""
        for speaker, message, file_data, file_name in chat_history:  # Se añade file_data y file_name
            full_prompt += f"{speaker}: {message}\n"
            if file_name:
                full_prompt += f"{speaker}: Archivo adjunto: {file_name}\n"
        
        if uploaded_file:
             file_name = uploaded_file.name
             file_data = uploaded_file.read()
             # Agrega información del archivo al prompt
             full_prompt += f"Usuario: Archivo adjunto: {file_name}\n"

             if file_name.lower().endswith(('.pdf', '.txt', '.csv', '.docx','.xlsx')):
                 try:
                     file_content = read_file_content(file_data,file_name)  # leer el contenido basado en la extensión
                     full_prompt += f"Usuario: Contenido del archivo: {file_content[:1000]}...\n"  # Limitar para que no sea demasiado extenso
                 except Exception as e:
                     print(f"Error al leer el contenido del archivo: {e}")
                     full_prompt += "Usuario: No se pudo procesar el archivo.\n"
        full_prompt += f"Usuario: {prompt}\n"

        print("Prompt generado:", full_prompt)
        if prompt.lower().startswith("genera código") or prompt.lower().startswith("code"):
            response = code_model.generate_content(full_prompt)
        else:
            response = model.generate_content(full_prompt)
        print("Respuesta API recibida:", response)
        if response.text:
            return response.text
        else:
            return "No se pudo generar respuesta."
    except Exception as e:
        print("Error en generate_response:", e)
        return f"Ocurrió un error al interactuar con la API: {e}"

def read_file_content(file_data, file_name):
  
    try:
        if file_name.lower().endswith('.txt'):
            return io.TextIOWrapper(io.BytesIO(file_data), encoding='utf-8').read()
        elif file_name.lower().endswith('.pdf'):
            import pypdf
            pdf_reader = pypdf.PdfReader(io.BytesIO(file_data))
            text = ""
            for page_num in range(len(pdf_reader.pages)):
                text += pdf_reader.pages[page_num].extract_text()
            return text
        elif file_name.lower().endswith('.csv'):
            import pandas as pd
            df = pd.read_csv(io.BytesIO(file_data))
            return df.to_string()
        elif file_name.lower().endswith('.docx'):
            import docx
            doc = docx.Document(io.BytesIO(file_data))
            text = '\n'.join([paragraph.text for paragraph in doc.paragraphs])
            return text
        elif file_name.lower().endswith('.xlsx'):
            import pandas as pd
            excel_file = pd.ExcelFile(io.BytesIO(file_data))
            all_sheets_text = ""
            for sheet_name in excel_file.sheet_names:
              df = excel_file.parse(sheet_name)
              all_sheets_text+= f"Hoja: {sheet_name} \n {df.to_string()} \n"
            return all_sheets_text
        else:
            return "Formato de archivo no compatible."
    except Exception as e:
       print(f"Error al leer el archivo: {e}")
       return f"Error al procesar el archivo: {e}"


# --- Interfaz de Streamlit ---
st.title("Chat con Gemini")

# Inicializamos el chat como un objeto
if 'chat' not in st.session_state:
    st.session_state['chat'] = Chat()
chat = st.session_state['chat']

# --- Layout de la interfaz ---
with st.sidebar:
    st.header("Chats")
    all_chats = chat.get_all_chats()
    if all_chats:
        for chat_name, chat_id in all_chats:
            col1, col2 = st.columns([0.8, 0.2])
            with col1:
                if st.button(chat_name, key=f"chat_{chat_id}", use_container_width=True):
                    st.session_state['selected_chat_id'] = chat_id
                    st.session_state['selected_chat_name'] = chat_name
            with col2:
                if st.button("🗑️", key=f"delete_{chat_id}", use_container_width=True):
                    chat.delete_chat(chat_id)
                    st.rerun()
        if st.button("Nuevo Chat"):
            st.session_state['creating_new_chat'] = True
    else:
        if st.button("Nuevo Chat"):
             st.session_state['creating_new_chat'] = True

# Área de entrada de texto
col1, col2 = st.columns([0.8, 0.2])
with col1:
    user_input = st.chat_input("Escribe tu mensaje aquí:", key=f'chat_input_{st.session_state.get("selected_chat_id", 0)}')
with col2:
   uploaded_file = st.file_uploader("Cargar archivo", type=['pdf', 'txt', 'csv', 'docx','xlsx'], key=f'file_uploader_{st.session_state.get("selected_chat_id", 0)}')

# Lógica del chat
if user_input or uploaded_file:
    if st.session_state.get('creating_new_chat', False):
      if user_input:
        chat.create_chat_with_first_message(user_input)
      elif uploaded_file:
        chat.create_chat_with_first_message(f"Archivo subido: {uploaded_file.name}") #Crea el chat con el nombre del archivo si no hay pregunta
      st.session_state['creating_new_chat'] = False

    
    if user_input:
      chat.add_message("Usuario", user_input, file_data=None, file_name=None) #Guardar mensaje del usuario sin archivos adjuntos
      generated_text = generate_response(user_input, chat.get_history(), uploaded_file)
    elif uploaded_file:
      chat.add_message("Usuario", f"Archivo subido: {uploaded_file.name}", file_data=uploaded_file.read(), file_name=uploaded_file.name) #Guardar el archivo subido
      generated_text = generate_response(f"Procesar archivo: {uploaded_file.name}", chat.get_history(), uploaded_file)
    else:
      generated_text = "No se recibió mensaje o archivo adjunto."


    chat.add_message("Assistant", generated_text)
    print("Texto generado:", generated_text)

    # Mostrar la respuesta
    with st.chat_message("assistant"):
        st.write(generated_text)


# Mostrar el historial del chat
for speaker, message, file_data, file_name in chat.get_history():  # Modificado para obtener file_data y file_name
    with st.chat_message(speaker):
      st.write(message)  
      if file_name:
           st.write(f"Archivo adjunto: {file_name}")
           if file_data:
            if file_name.lower().endswith(('.pdf', '.txt', '.csv', '.docx','.xlsx')):
                 try:
                    st.download_button(
                     label="Descargar archivo",
                     data=file_data,
                     file_name=file_name,
                     key=f"download_{file_name}"
                    )
                 except Exception as e:
                     st.write(f"Error al cargar archivo para descargar: {e}")


if st.session_state['selected_chat_id'] is not None and st.session_state['selected_chat_name']:
    st.header(f"Chat: {st.session_state['selected_chat_name']}")
