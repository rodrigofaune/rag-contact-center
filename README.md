# Agente RAG de Vertex AI con ADK y API FastAPI

Este repositorio contiene una implementación del Google Agent Development Kit (ADK) de un agente de Recuperación Aumentada por Generación (RAG) usando Google Cloud Vertex AI, con una API FastAPI que permite el acceso desde aplicaciones frontend con soporte completo para CORS.

## Descripción general

El Agente RAG de Vertex AI te permite:

- Consultar corpora de documentos con preguntas en lenguaje natural
- Listar los corpora de documentos disponibles
- Crear nuevos corpora de documentos
- Agregar nuevos documentos a corpora existentes
- Obtener información detallada sobre corpora específicos
- Eliminar corpora cuando ya no sean necesarios
- **Acceder a todas las funcionalidades desde aplicaciones web frontend mediante una API REST con CORS habilitado**

## Prerrequisitos

- Una cuenta de Google Cloud con facturación habilitada
- Un proyecto de Google Cloud con la API de Vertex AI habilitada
- Acceso adecuado para crear y administrar recursos de Vertex AI
- Entorno Python 3.12+

## Configuración de la autenticación de Google Cloud

Antes de ejecutar el agente, necesitas configurar la autenticación con Google Cloud:

1. **Instala Google Cloud CLI**:
   - Visita [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) para instrucciones de instalación según tu sistema operativo

   Nota: Por ahora, RAG y ciertos modelos de Gemini no están disponibles en los servidores de Brasil. Se recomienda usar us-central1 por defecto.

2. **Inicializa Google Cloud CLI**:
   ```bash
   gcloud init
   ```
   Esto te guiará para iniciar sesión y seleccionar tu proyecto.

3. **Configura las Credenciales de Aplicación Predeterminadas**:
   ```bash
   gcloud auth application-default login
   ```
   Esto abrirá una ventana del navegador para autenticación y almacenará las credenciales en:
   `~/.config/gcloud/application_default_credentials.json`

4. **Verifica la autenticación**:
   ```bash
   gcloud auth list
   gcloud config list
   ```

5. **Habilita las APIs requeridas** (si aún no están habilitadas):
   ```bash
   gcloud services enable aiplatform.googleapis.com
   ```

## Instalación

1. **Configura un entorno virtual**:
   ```bash
   python -m venv .venv #Si tienes problemas para usar python 12 usa  ~/.pyenv/versions/3.12.3/bin/python -m venv .venv 
   source .venv/bin/activate  # En Windows: .venv\Scripts\activate
   ```

2. **Instala las dependencias**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configura las variables de entorno**:
   Copia el archivo `.env.example` a `.env` y configura las variables necesarias:
   ```bash
   cp .env.example .env
   ```
   
   Luego edita el archivo `.env` con tus valores:
   ```
   GOOGLE_CLOUD_PROJECT="tu-proyecto-id"
   GOOGLE_CLOUD_LOCATION="us-central1"
   GOOGLE_GENAI_USE_VERTEXAI="True"
   GOOGLE_API_KEY="tu-api-key-de-google"
   DRIVE_FOLDER_ID="id-de-carpeta-de-google-drive"
   ```

   **Nota**: Para usar la funcionalidad de carga masiva desde Google Drive, necesitas:
   - `GOOGLE_API_KEY`: Una clave de API de Google con acceso a Google Drive API
   - `DRIVE_FOLDER_ID`: El ID de la carpeta de Google Drive que contiene tus documentos

## Uso de la API FastAPI (Recomendado)

La forma más fácil de usar el agente es a través de la API FastAPI que incluye soporte completo para CORS, permitiendo el acceso desde aplicaciones frontend.

### Inicio rápido

1. **Ejecuta el servidor**:
   ```bash
   # Usando el script de inicio (recomendado)
   ./start_server.sh
   
   # O directamente con Python
   python server.py
   ```

2. **El servidor estará disponible en**:
   - API principal: `http://localhost:8000`
   - Documentación interactiva: `http://localhost:8000/docs`
   - Health check: `http://localhost:8000/health`

### Endpoints principales

#### POST `/chat`
Endpoint principal para chatear con el agente RAG:
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "¿Qué información tienes sobre el tema X?",
    "user_id": "user_123",
    "session_id": "session_456"
  }'
```

#### GET/POST `/apps/rag_agent/users/{user_id}/sessions/{session_id}`
Compatible con el patrón de URL que mencionaste en tu error:
```bash
# GET - Obtener historial de sesión
curl "http://localhost:8000/apps/rag_agent/users/user_123/sessions/session_456"

# POST - Enviar mensaje a una sesión específica
curl -X POST "http://localhost:8000/apps/rag_agent/users/user_123/sessions/session_456" \
  -H "Content-Type: application/json" \
  -d '{"message": "Tu pregunta aquí"}'
```

### Uso desde Frontend JavaScript/React

```javascript
// Ejemplo básico de uso desde React/JavaScript
const sendMessage = async (message, userId, sessionId) => {
  try {
    const response = await fetch('http://localhost:8000/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: message,
        user_id: userId,
        session_id: sessionId
      })
    });
    
    const data = await response.json();
    return data.response;
  } catch (error) {
    console.error('Error:', error);
  }
};

// Usar la función
const answer = await sendMessage(
  "¿Qué documentos tienes disponibles?", 
  "user_123", 
  "session_456"
);
```

### CORS configurado para

- `http://localhost:3000` (React/Next.js dev server)
- `http://localhost:3001` (puerto alternativo)
- `http://localhost:5173` (Vite dev server)
- `http://127.0.0.1:3000` y `http://127.0.0.1:5173`

## Uso del agente (Programático)

El agente proporciona la siguiente funcionalidad a través de sus herramientas:

### 1. Consultar documentos
Te permite hacer preguntas y obtener respuestas de tu corpus de documentos:
- Recupera automáticamente información relevante del corpus especificado
- Genera respuestas informativas basadas en el contenido recuperado

### 2. Listar corpora
Muestra todos los corpora de documentos disponibles en tu proyecto:
- Muestra los nombres de los corpora y la información básica
- Te ayuda a entender qué colecciones de datos están disponibles

### 3. Crear corpus
Crea un nuevo corpus de documentos vacío:
- Especifica un nombre personalizado para tu corpus
- Configura el corpus con la configuración recomendada del modelo de embeddings
- Prepara el corpus para la ingestión de documentos

### 4. Agregar nuevos datos
Agrega documentos a corpora existentes o crea nuevos:
- Soporta URLs de Google Drive y rutas de GCS (Google Cloud Storage)
- Crea automáticamente nuevos corpora si no existen

### 5. Obtener información del corpus
Proporciona información detallada sobre un corpus específico:
- Muestra el conteo de documentos, metadatos de archivos y fecha de creación
- Útil para entender el contenido y la estructura del corpus

### 6. Eliminar corpus
Elimina corpora que ya no sean necesarios:
- Requiere confirmación para evitar eliminaciones accidentales
- Elimina permanentemente el corpus y todos los archivos asociados

### 7. Carga masiva desde Google Drive
Permite subir documentos masivamente desde una carpeta de Google Drive:
- Explora recursivamente todas las subcarpetas de una carpeta de Google Drive
- Sube automáticamente todos los documentos encontrados al corpus especificado
- Soporta vista previa de contenidos antes de la carga
- Convierte URLs de Google Docs/Sheets/Slides al formato Drive compatible

## Resolución de problemas

Si encuentras problemas:

- **Problemas de autenticación**:
  - Ejecuta `gcloud auth application-default login` nuevamente
  - Verifica que tu cuenta de servicio tenga los permisos necesarios

- **Errores de API**:
  - Asegúrate de que la API de Vertex AI esté habilitada: `gcloud services enable aiplatform.googleapis.com`
  - Verifica que tu proyecto tenga la facturación habilitada

- **Problemas de cuota**:
  - Revisa en la Consola de Google Cloud si tienes limitaciones de cuota
  - Solicita aumentos de cuota si es necesario

- **Dependencias faltantes**:
  - Asegúrate de que todas las dependencias estén instaladas: `pip install -r requirements.txt`

## Ejemplo de uso - Carga masiva desde Google Drive

Para usar la nueva funcionalidad de carga masiva, puedes usar las funciones directamente en tu código:

```python
from google.adk.tools.tool_context import ToolContext
from rag_agent.tools import bulk_upload_drive, get_drive_folder_contents

# Crear contexto de herramienta
tool_context = ToolContext()

# Vista previa de contenidos (opcional)
preview = get_drive_folder_contents(
    tool_context=tool_context,
    include_subfolders=True,
    max_files=100
)

# Carga masiva de documentos
result = bulk_upload_drive(
    corpus_name="mi-corpus",
    tool_context=tool_context,
    include_subfolders=True,
    max_files=1000
)
```

## Recursos adicionales

- [Documentación de Vertex AI RAG](https://cloud.google.com/vertex-ai/generative-ai/docs/rag-overview)
- [Documentación de Google Agent Development Kit (ADK)](https://github.com/google/agents-framework)
- [Guía de autenticación de Google Cloud](https://cloud.google.com/docs/authentication)