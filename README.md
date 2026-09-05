# SkeletIA — Modelo relacional y análisis en Google BigQuery

## Descripción del proyecto

**SkeletIA** es un proyecto de modelado y análisis de datos para un e-commerce de productos tecnológicos que opera en varios países de Europa.

El punto de partida del caso de negocio es una empresa que trabaja con hojas de cálculo y archivos CSV dispersos y necesita centralizar su información en una base de datos que permita gestionar el catálogo, los pedidos, los pagos y las valoraciones, además de realizar análisis sobre ventas, rentabilidad, clientes y tendencias.

El proyecto se implementa mediante un modelo relacional en **Google BigQuery**, con generación de datos sintéticos en **Python + Faker**, validación mediante `pandas` y consultas analíticas desarrolladas en Jupyter Notebooks.

---

## Objetivos de negocio

El modelo permite cubrir dos grandes áreas.

### Control operativo

- Gestionar el catálogo de productos y sus categorías.
- Registrar pedidos y sus líneas de producto.
- Controlar los estados de los pedidos.
- Gestionar pagos y sus incidencias.
- Mantener información de stock.
- Registrar valoraciones asociadas a compras concretas.

### Análisis del negocio

- Analizar qué clientes compran cada producto.
- Calcular ingresos, costes y márgenes.
- Analizar rentabilidad por categoría.
- Segmentar clientes por país y canal de adquisición.
- Analizar el comportamiento de los métodos de pago.
- Medir tiempos de entrega.
- Analizar valoraciones de productos.
- Identificar tendencias temporales de ventas.
- Analizar recurrencia, valor de cliente y comportamiento de compra.

---

## Modelo de datos

La implementación final de SkeletIA está formada por **11 tablas**:

| Tabla | Función |
|---|---|
| `countries` | Países del modelo |
| `cities` | Ciudades asociadas a los países |
| `acquisition_channels` | Canales de adquisición de clientes |
| `categories` | Categorías del catálogo |
| `brands` | Marcas de productos |
| `customers` | Información principal de clientes |
| `products` | Catálogo actual de productos |
| `orders` | Cabecera de los pedidos |
| `order_items` | Líneas de producto de cada pedido |
| `payments` | Información de pagos |
| `reviews` | Valoraciones asociadas a líneas de pedido |

La relación N:M entre `orders` y `products` se resuelve mediante `order_items`.

El modelo diferencia además entre los datos actuales del catálogo y los valores históricos de cada venta:

- `products.current_sale_price`: precio actual.
- `products.current_cost`: coste actual.
- `order_items.unit_price`: precio histórico de venta.
- `order_items.unit_cost`: coste histórico asociado a la venta.
- `order_items.discount_percent`: descuento aplicado a esa línea concreta.

Esta separación permite conservar correctamente el histórico económico aunque los precios o costes actuales cambien.

---

## Normalización

El modelo se ha diseñado para cumplir como mínimo:

- **1NF — Primera Forma Normal**
- **2NF — Segunda Forma Normal**
- **3NF — Tercera Forma Normal**

Además, se ha revisado respecto a:

- **BCNF**
- **4NF**
- **5NF**

La justificación detallada se encuentra en:

```text
parte_2_modelo_bigquery/docs/normalizacion.md
```

Las decisiones generales de arquitectura y modelado se documentan en:

```text
parte_2_modelo_bigquery/docs/modelo_diseno.md
```

El diagrama entidad-relación se encuentra en:

```text
parte_2_modelo_bigquery/docs/skeletia_er.png
```

---

## Stack tecnológico

El proyecto utiliza:

- Python
- Google BigQuery
- Jupyter Notebooks
- pandas
- Faker
- Google Cloud BigQuery Client
- python-dotenv
- Git
- GitHub
- `venv` para el entorno virtual

Las dependencias Python necesarias son:

```text
google-cloud-bigquery
google-auth
db-dtypes
pandas
faker
python-dotenv
pyarrow
```

Todas deben estar incluidas en `requirements.txt`.

---

## Estructura del repositorio

```text
tc-sql-bometon/
├── parte_1_sql_murder_mystery/
│   └── investigacion.ipynb
│
├── parte_2_modelo_bigquery/
│   ├── data/
│   │
│   ├── docs/
│   │   ├── er_diagram.png
│   │   ├── normalizacion.md
│   │   └── modelo_diseno.md
│   │
│   └── notebooks/
│       ├── 01_setup_bigquery.ipynb
│       ├── 02_generate_data.ipynb
│       └── 03_queries_verification.ipynb
│
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

Los datos finales se almacenan en BigQuery. La carpeta `data/` no necesita contener una copia local de los datos cargados.

---

# Configuración del proyecto

## 1. Clonar el repositorio

```bash
git clone <URL_DEL_REPOSITORIO>
cd tc-sql-bometon
```

---

## 2. Crear el entorno virtual

Desde la raíz del proyecto:

### macOS / Linux

```bash
python -m venv venv
source venv/bin/activate
```

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

---

## 3. Instalar las dependencias

```bash
pip install -r requirements.txt
```

Para comprobar la instalación:

```bash
pip list
```

---

# Configuración de Google Cloud

## 4. Crear o configurar un proyecto de Google Cloud

Es necesario disponer de un proyecto de Google Cloud con acceso a BigQuery.

Pasos:

1. Crear un proyecto en Google Cloud.
2. Activar la API de BigQuery.
3. Crear un **Service Account**.
4. Asignarle el rol `BigQuery Admin`.
5. Crear y descargar una clave JSON.
6. Guardar la clave dentro de una carpeta local:

```text
credentials/
```

Ejemplo:

```text
credentials/service-account.json
```

La carpeta `credentials/` no debe subirse al repositorio.

---

## 5. Variables de entorno

Crear un archivo `.env` en la raíz del proyecto utilizando `.env.example` como plantilla.

Ejemplo:

```env
GCP_PROJECT_ID=tu-proyecto-gcp
BQ_DATASET_ID=skeletia
GOOGLE_APPLICATION_CREDENTIALS=./credentials/service-account.json
```

El archivo `.env` contiene configuración local y no debe versionarse.

---

# Ejecución de los notebooks

Los notebooks deben ejecutarse en este orden:

```text
01_setup_bigquery.ipynb
        ↓
02_generate_data.ipynb
        ↓
03_queries_verification.ipynb
```

Cada notebook crea su propia conexión a BigQuery utilizando las variables definidas en `.env`.

---

## 01 — Setup de BigQuery

Archivo:

```text
parte_2_modelo_bigquery/notebooks/01_setup_bigquery.ipynb
```

Responsabilidades principales:

- cargar la configuración del entorno;
- conectarse a Google BigQuery;
- crear el dataset;
- definir los esquemas;
- crear las tablas respetando sus dependencias;
- validar que la estructura se ha creado correctamente.

El dataset utilizado por el proyecto es:

```text
skeletia
```

---

## 02 — Generación y carga de datos

Archivo:

```text
parte_2_modelo_bigquery/notebooks/02_generate_data.ipynb
```

La generación utiliza **Python + Faker**.

Volúmenes generados:

| Entidad | Volumen |
|---|---:|
| Clientes | 500 |
| Productos | 70 |
| Pedidos | 2.000 |
| Líneas de pedido | 4.500 |
| Pagos | 1 por pedido |
| Reviews | Aproximadamente el 35 % de las líneas correspondientes a pedidos entregados |

Los datos se generan primero en memoria y después se convierten en DataFrames de pandas.

Antes de realizar la carga se validan, entre otras cuestiones:

- claves primarias;
- claves foráneas;
- valores únicos;
- estados permitidos;
- rangos numéricos;
- coherencia temporal;
- coherencia entre pedidos y pagos;
- importes económicos;
- relaciones entre pedidos, líneas y reviews.

Después de las validaciones, las tablas se cargan en BigQuery respetando el orden de sus dependencias.

Orden de carga:

```text
countries
cities
acquisition_channels
categories
brands
customers
products
orders
order_items
payments
reviews
```

Tras la carga se compara el número de filas de cada DataFrame con el número de filas almacenadas en BigQuery.

---

## Métodos de pago

Los métodos de pago definidos en el modelo son:

```text
apple_pay
bank_transfer
card
cash_on_delivery
google_pay
paypal
samsung_pay
```

Los estados de pago utilizados son:

```text
pending
completed
failed
refunded
```

---

## Estados de pedido

Los estados permitidos son:

```text
pending
confirmed
shipped
delivered
cancelled
returned
```

---

# 03 — Queries de verificación

Archivo:

```text
parte_2_modelo_bigquery/notebooks/03_queries_verification.ipynb
```

El enunciado exige al menos cinco consultas analíticas que demuestren que el modelo funciona.

El notebook amplía ese mínimo con consultas de nivel intermedio y avanzado.

Actualmente se incluyen los siguientes análisis:

1. Ingresos mensuales.
2. Productos más vendidos.
3. Clientes por país.
4. Tiempos de preparación y entrega.
5. Ingresos, costes y margen por categoría.
6. Top 3 productos por facturación dentro de cada categoría.
7. Segmentación de clientes por valor.
8. Tasa de repetición de compra por canal de adquisición.
9. Tiempo desde el registro hasta la primera compra por canal.
10. Rendimiento de los métodos de pago.
11. Tasa de cancelaciones y devoluciones por categoría.
12. Comparación entre precio histórico y precio actual.
13. Productos comprados juntos con mayor frecuencia — Market Basket Analysis.
14. Riesgo de rotura de stock según demanda reciente.

Las consultas utilizan, entre otros:

- agregaciones;
- `JOIN`;
- `LEFT JOIN`;
- `SELF JOIN`;
- CTE;
- funciones de fecha;
- agregaciones condicionales;
- `SAFE_DIVIDE`;
- `CASE`;
- funciones de ventana;
- `DENSE_RANK`;
- `PARTITION BY`;
- percentiles.

---

# Reproducibilidad

La generación utiliza una semilla aleatoria para favorecer la reproducibilidad de los datos.

El flujo completo esperado es:

```text
Creación del esquema
        ↓
Generación de datos sintéticos
        ↓
Creación de DataFrames
        ↓
Validación
        ↓
Carga en BigQuery
        ↓
Verificación de la carga
        ↓
Consultas analíticas
```

---

# Seguridad y credenciales

No deben subirse al repositorio:

```text
.env
credentials/
venv/
```

El repositorio sí debe incluir:

```text
.env.example
.gitignore
requirements.txt
```

`.env.example` debe contener únicamente la estructura de las variables necesarias, sin credenciales reales.

---

# Archivos requeridos para la entrega

El repositorio debe contener:

- notebook de investigación de la Parte I;
- diagrama entidad-relación;
- notebooks completos y ejecutables de la Parte II;
- `README.md` con instrucciones de setup;
- `requirements.txt` actualizado;
- `.env.example`;
- `.gitignore`;
- documentación de normalización;
- historial de commits descriptivo.

El repositorio debe ser accesible para su revisión.

---

# Flujo de trabajo con Git

Se recomienda trabajar con commits pequeños y descriptivos.

Ejemplos:

```text
feat: crear esquema de tabla customers
fix: corregir FK de order_items
docs: añadir justificación de 3NF
```

Antes de realizar la entrega final conviene comprobar:

```bash
git status
git log --oneline
```

y confirmar que ningún archivo de credenciales está versionado.

---

# Documentación adicional

La documentación del modelo se encuentra en:

```text
parte_2_modelo_bigquery/docs/
```

Incluye:

- `skeletia_er.png`: diagrama entidad-relación.
- `normalizacion.md`: justificación de normalización y dependencias.
- `modelo_diseno.md`: descripción del modelo y decisiones de diseño.

---

## Nota sobre el bonus

El enunciado propone de forma opcional la creación de un script CLI `seed.py` para regenerar la base de datos desde línea de comandos.

Este elemento es un **bonus opcional** y no forma parte de los requisitos mínimos de la entrega.
