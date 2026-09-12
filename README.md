# Forensic Auditor 🔍⚡
> **Hub de Auditoría Forense y Detección Determinista de Lavado de Dinero (AML)**

Plataforma monorepo de alto rendimiento para el análisis forense de transacciones financieras basada en el dataset IBM AMLSim. Combina **poda determinista basada en teoría de grafos** (Polars + NetworkX) para reducir el ruido en hasta un 95%, **Server-Sent Events (SSE)** para streaming de razonamiento pericial en tiempo real (conector con n8n) y **síntesis de voz pericial protegida** con ElevenLabs.

---

## 🏛️ Arquitectura del Sistema

```
                         [ CSV Dataset (IBM AMLSim) ]
                                      │
                                      ▼
               ┌──────────────────────────────────────────────┐
               │         Backend (FastAPI + Polars)           │
               │  - Ingesta y normalización en memoria        │
               │  - Construcción de grafo dirigido (NetworkX) │
               │  - Poda determinista (Ciclos & Cuentas Mula) │
               └──────────────────────┬───────────────────────┘
                                      │
                 ┌────────────────────┴────────────────────┐
                 ▼                                         ▼
   [ SSE Thoughts Stream ]                       [ Subgrafo Filtrado ]
   - Conexión n8n / Fallback Local               - Nodos Críticos
   - Inferencia Pericial Paso a Paso             - Métricas de Riesgo
                 │                                         │
                 └────────────────────┬────────────────────┘
                                      │
                                      ▼
               ┌──────────────────────────────────────────────┐
               │        Frontend (Next.js App Router)         │
               │  - FileUpload (Drag & Drop)                  │
               │  - ThoughtStream (Consola Terminal SSE)      │
               │  - VerdictCard (Dictamen + Métricas)         │
               │  - AudioPlayer (Streaming ElevenLabs Proxy)  │
               └──────────────────────────────────────────────┘
```

---

## 📁 Estructura del Repositorio

```text
HackMty2026-InfoSys/
├── backend/                        # API en Python con FastAPI
│   ├── api/
│   │   └── routes/
│   │       ├── investigations.py   # Upload CSV, poda y endpoint SSE stream
│   │       └── tts.py              # Proxy seguro para streaming de audio ElevenLabs
│   ├── core/
│   │   └── config.py               # Configuración centralizada con Pydantic Settings
│   ├── services/
│   │   ├── ingestion.py            # Ingesta normalizada con Polars
│   │   └── deterministic_filter.py # Algoritmos NetworkX (ciclos y cuentas 90% <48h)
│   ├── tests/
│   │   └── test_pipeline.py        # Pruebas e2e con pytest y httpx.AsyncClient
│   ├── .env.example                # Variables de entorno para backend
│   ├── Dockerfile                  # Contenedor backend
│   ├── main.py                     # Entrypoint de FastAPI y CORS
│   └── requirements.txt            # Dependencias Python
│
├── frontend/                       # Frontend en Next.js con Tailwind CSS
│   ├── app/
│   │   ├── globals.css             # Estilos globales y scrollbars dark mode
│   │   ├── layout.tsx              # Layout raíz
│   │   └── page.tsx                # Dashboard principal integrado
│   ├── components/
│   │   ├── AudioPlayer.tsx         # Reproductor de voz streaming
│   │   ├── FileUpload.tsx          # Drag-and-drop para datasets AMLSim
│   │   ├── ThoughtStream.tsx       # Consola colapsable tipo terminal SSE
│   │   └── VerdictCard.tsx         # Tarjeta de dictamen pericial forense
│   ├── hooks/
│   │   ├── useAudioStream.ts       # Hook para consumo de audio stream
│   │   └── useInvestigationStream.ts# Hook para consumo de Server-Sent Events
│   ├── lib/
│   │   └── utils.ts                # Clsx, twMerge y formateadores de moneda
│   ├── types/
│   │   └── investigation.ts        # Tipos TypeScript compartidos
│   ├── .env.example                # Variables de entorno frontend
│   ├── Dockerfile                  # Contenedor frontend
│   ├── next.config.js              # Configuración Next.js
│   ├── package.json                # Dependencias Node.js
│   ├── postcss.config.js           # PostCSS
│   ├── tailwind.config.js          # Configuración Tailwind CSS
│   └── tsconfig.json               # Configuración TypeScript
│
├── data/
│   └── sample_amlsim.csv           # Dataset sintético de prueba inmediata
├── docker-compose.yml              # Orquestación con PostgreSQL (pgvector) y n8n
└── README.md                       # Documentación técnica
```

---

## 🚀 Comandos de Inicialización y Ejecución

### 1. Backend (FastAPI)

```bash
# Navegar al directorio del backend
cd backend

# Crear entorno virtual (Recomendado)
python -m venv venv

# Activar entorno virtual
# En Windows:
.\venv\Scripts\activate
# En Linux/macOS:
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env

# Ejecutar el servidor de desarrollo
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```
La documentación Swagger interactiva quedará disponible en: `http://localhost:8000/api/v1/docs`

### 2. Ejecución de Pruebas Unitarias y E2E

```bash
# Desde la raíz del repositorio:
python -m pytest backend/tests/test_pipeline.py -v
```

### 3. Frontend (Next.js)

```bash
# Navegar al directorio del frontend
cd frontend

# Instalar dependencias
npm install

# Configurar variables de entorno
cp .env.example .env.local

# Ejecutar servidor de desarrollo
npm run dev
```
La interfaz de usuario quedará accesible en: `http://localhost:3000`

---

## 🧠 Algoritmos Deterministas Implementados

1. **Detección de Ciclos Cerrados Dirigidos (`detect_closed_cycles`):**
   - Utiliza `nx.simple_cycles` acotado por `MAX_CYCLE_LENGTH` para aislar circuitos de estratificación (*layering/smurfing*), donde los fondos recirculan para ocultar su origen.
2. **Cuentas de Alta Velocidad y Paso Rápido (`detect_passthrough_accounts`):**
   - Identifica nodos con flujos bidireccionales donde:
     $$\frac{\min(\text{Inflow}, \text{Outflow})}{\max(\text{Inflow}, \text{Outflow})} \ge 0.90$$
     dentro de una ventana temporal $\Delta t \le 48 \text{ horas}$.
3. **Poda Topológica Determinista:**
   - Aísla el subgrafo sospechoso $G_{\text{suspect}}$ y descarta operaciones legítimas (nóminas, compras retail, micro-pagos), logrando entre 85% y 98% de reducción de ruido computacional antes de alimentar al LLM.