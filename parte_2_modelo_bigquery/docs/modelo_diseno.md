# Documentación del modelo y decisiones de diseño — SkeletIA

## 1. Objetivo del documento

Este documento describe el modelo de datos de **SkeletIA**, un e-commerce de productos tecnológicos, y recoge las principales decisiones de diseño y arquitectura adoptadas durante su implementación.

El objetivo es explicar **qué representa cada tabla, cómo se relacionan las entidades, qué reglas de negocio se han aplicado y por qué se ha elegido esta estructura**.

La justificación formal de las formas normales se desarrolla de manera específica en [`normalizacion.md`](normalizacion.md). Este documento se centra principalmente en la arquitectura general del modelo y en las decisiones de diseño que condicionan su funcionamiento.

---

## 2. Visión general del sistema

La solución se ha diseñado como un modelo relacional implementado en **Google BigQuery**.

La generación y preparación de datos se realiza en **Python**, utilizando `pandas` y `Faker`. Antes de cargar los datos en BigQuery se ejecutan validaciones para comprobar la integridad estructural y las principales reglas de negocio.

El flujo general del proyecto es:

```text
Definición del modelo
        ↓
Creación del dataset y tablas en BigQuery
        ↓
Generación de datos sintéticos con Python + Faker
        ↓
Creación de DataFrames
        ↓
Validación de los datos
        ↓
Carga en BigQuery
        ↓
Verificación de la carga
        ↓
Consultas analíticas
```

La base de datos está formada por **11 tablas**.

---

## 3. Diagrama entidad-relación

El modelo completo puede consultarse en el diagrama ER generado para el proyecto:

![Diagrama entidad-relación de SkeletIA](er_diagram.png)

El diagrama muestra las tablas, sus campos, las claves primarias y foráneas y las cardinalidades entre las distintas entidades.

---

## 4. Organización del modelo

Las tablas pueden agruparse conceptualmente en tres bloques.

| Grupo | Tablas | Función |
|---|---|---|
| Datos maestros y de referencia | `countries`, `cities`, `acquisition_channels`, `categories`, `brands` | Contienen información reutilizable por otras entidades y evitan repetir valores descriptivos |
| Entidades principales de negocio | `customers`, `products`, `orders` | Representan clientes, catálogo y pedidos |
| Entidades transaccionales | `order_items`, `payments`, `reviews` | Representan líneas de compra, pagos y valoraciones |

Esta separación permite mantener las responsabilidades de cada tabla bien delimitadas y evita mezclar datos maestros con datos transaccionales.

---

# 5. Descripción de las tablas

## 5.1 `countries`

Representa los países utilizados por el sistema.

| Campo | Función |
|---|---|
| `country_id` | Clave primaria numérica |
| `country_code` | Código del país |
| `country_name` | Nombre del país |

Los países se almacenan en una tabla independiente para evitar repetir el nombre y el código del país en clientes, ciudades o pedidos.

La relación principal es:

```text
countries 1 ───── N cities
```

Un país puede tener muchas ciudades y cada ciudad pertenece a un único país.

---

## 5.2 `cities`

Representa las ciudades disponibles en el modelo.

| Campo | Función |
|---|---|
| `city_id` | Clave primaria |
| `country_id` | FK hacia `countries` |
| `city_name` | Nombre de la ciudad |

La combinación:

```text
(country_id, city_name)
```

se considera única dentro del modelo.

Esto permite que dos países diferentes puedan tener ciudades con el mismo nombre, pero evita registrar dos veces la misma ciudad dentro de un mismo país.

`cities` se utiliza tanto para localizar clientes como para representar la ciudad de destino de los pedidos.

---

## 5.3 `acquisition_channels`

Representa el canal mediante el que un cliente fue adquirido.

| Campo | Función |
|---|---|
| `channel_id` | Clave primaria |
| `channel_code` | Código interno del canal |
| `channel_name` | Nombre descriptivo |

Los canales utilizados en los datos sintéticos son, entre otros:

```text
organic
paid_ads
social_media
referral
affiliate
```

La relación es:

```text
acquisition_channels 1 ───── N customers
```

Separar los canales en una tabla propia facilita posteriormente analizar el rendimiento de adquisición de clientes.

---

## 5.4 `categories`

Representa las categorías del catálogo.

| Campo | Función |
|---|---|
| `category_id` | Clave primaria |
| `category_name` | Nombre de la categoría |
| `description` | Descripción opcional |

La relación es:

```text
categories 1 ───── N products
```

Una categoría puede contener muchos productos, mientras que cada producto pertenece a una categoría.

El nombre de la categoría no se almacena directamente en `products`; se utiliza `category_id` como FK.

---

## 5.5 `brands`

Representa las marcas de los productos.

| Campo | Función |
|---|---|
| `brand_id` | Clave primaria |
| `brand_name` | Nombre de la marca |

La relación es:

```text
brands 1 ───── N products
```

Una marca puede tener muchos productos y cada producto pertenece a una única marca.

---

## 5.6 `customers`

Representa los clientes registrados.

| Campo | Función |
|---|---|
| `customer_id` | Clave primaria |
| `first_name` | Nombre |
| `last_name` | Apellidos |
| `email` | Email del cliente |
| `phone` | Teléfono |
| `city_id` | FK hacia `cities` |
| `channel_id` | FK hacia `acquisition_channels` |
| `registered_at` | Fecha de registro |
| `is_active` | Indica si el cliente está activo |

Las relaciones principales son:

```text
cities 1 ───── N customers

acquisition_channels 1 ───── N customers

customers 1 ───── N orders
```

En `customers` no se repiten el nombre del país, el nombre de la ciudad ni el nombre del canal de adquisición. Estos valores se obtienen mediante sus respectivas relaciones.

---

## 5.7 `products`

Representa el catálogo actual de SkeletIA.

| Campo | Función |
|---|---|
| `product_id` | Clave primaria |
| `sku` | Identificador comercial único |
| `category_id` | FK hacia `categories` |
| `brand_id` | FK hacia `brands` |
| `product_name` | Nombre del producto |
| `current_sale_price` | Precio de venta actual |
| `current_cost` | Coste actual |
| `stock` | Stock disponible |
| `is_active` | Estado del producto |
| `created_at` | Fecha de creación |

Las relaciones principales son:

```text
categories 1 ───── N products

brands 1 ───── N products

products 1 ───── N order_items
```

Es importante distinguir entre los valores actuales del catálogo y los valores históricos de una venta concreta.

`current_sale_price` y `current_cost` representan únicamente el estado actual del producto.

Los precios y costes históricos se almacenan en `order_items`.

---

## 5.8 `orders`

Representa la cabecera de cada pedido.

| Campo | Función |
|---|---|
| `order_id` | Clave primaria |
| `customer_id` | FK hacia `customers` |
| `status` | Estado del pedido |
| `order_date` | Fecha del pedido |
| `shipped_at` | Fecha de envío |
| `delivered_at` | Fecha de entrega |
| `shipping_recipient` | Destinatario del envío |
| `shipping_address_line1` | Dirección utilizada para el envío |
| `shipping_postal_code` | Código postal |
| `shipping_city_id` | FK hacia `cities` |
| `shipping_cost` | Coste de envío |
| `currency_code` | Moneda del pedido |

Los estados admitidos en el modelo son:

```text
pending
confirmed
shipped
delivered
cancelled
returned
```

Las relaciones principales son:

```text
customers 1 ───── N orders

cities 1 ───── N orders

orders 1 ───── N order_items
```

En el alcance actual del proyecto se genera además un pago por cada pedido.

---

## 5.9 `order_items`

Representa las líneas de pedido.

| Campo | Función |
|---|---|
| `order_item_id` | Clave primaria |
| `order_id` | FK hacia `orders` |
| `product_id` | FK hacia `products` |
| `quantity` | Número de unidades |
| `unit_price` | Precio histórico de venta por unidad |
| `unit_cost` | Coste histórico por unidad |
| `discount_percent` | Descuento aplicado a esa línea |

Esta tabla resuelve la relación N:M existente entre pedidos y productos:

```text
orders
   1
   │
   N
order_items
   N
   │
   1
products
```

Un pedido puede contener muchos productos y un mismo producto puede aparecer en muchos pedidos.

La combinación:

```text
(order_id, product_id)
```

se considera única.

Si se compran varias unidades del mismo producto dentro de un pedido, se incrementa `quantity` en lugar de crear una segunda línea para ese mismo producto.

---

## 5.10 `payments`

Representa el proceso de pago asociado a los pedidos.

| Campo | Función |
|---|---|
| `payment_id` | Clave primaria |
| `order_id` | FK hacia `orders` |
| `payment_method` | Método de pago |
| `status` | Estado del pago |
| `amount` | Importe del pago |
| `payment_date` | Fecha del pago |
| `status_updated_at` | Última actualización del estado |
| `external_reference` | Referencia externa única |

Métodos de pago definidos:

```text
card
paypal
bank_transfer
apple_pay
google_pay
```

Estados de pago definidos:

```text
pending
completed
failed
refunded
```

En el conjunto de datos generado existe exactamente un pago por pedido.

Esta regla se valida durante la generación de datos.

---

## 5.11 `reviews`

Representa las valoraciones realizadas sobre productos comprados.

| Campo | Función |
|---|---|
| `review_id` | Clave primaria |
| `order_item_id` | FK hacia `order_items` |
| `rating` | Valoración entre 1 y 5 |
| `comment` | Comentario |
| `review_date` | Fecha de la valoración |

La relación lógica es:

```text
order_items 1 ───── 0..1 reviews
```

Una línea de pedido puede no tener valoración o tener una única valoración.

La review se asocia a una compra concreta mediante `order_item_id`.

No se almacenan directamente `product_id`, `order_id` ni `customer_id`, porque esos valores pueden recuperarse recorriendo las relaciones existentes.

---

# 6. Relaciones y cardinalidades

| Entidad origen | Relación | Entidad destino | Significado |
|---|---|---|---|
| `countries` | 1:N | `cities` | Un país puede contener muchas ciudades |
| `cities` | 1:N | `customers` | Una ciudad puede tener muchos clientes |
| `acquisition_channels` | 1:N | `customers` | Un canal puede adquirir muchos clientes |
| `categories` | 1:N | `products` | Una categoría puede contener muchos productos |
| `brands` | 1:N | `products` | Una marca puede contener muchos productos |
| `customers` | 1:N | `orders` | Un cliente puede realizar muchos pedidos |
| `cities` | 1:N | `orders` | Una ciudad puede ser destino de muchos pedidos |
| `orders` | 1:N | `order_items` | Un pedido contiene una o varias líneas |
| `products` | 1:N | `order_items` | Un producto puede aparecer en muchos pedidos |
| `orders` | 1:1 en el alcance actual | `payments` | Se genera un pago por pedido |
| `order_items` | 1:0..1 | `reviews` | Una compra concreta puede tener como máximo una review |

La relación N:M entre `orders` y `products` se resuelve mediante `order_items`.

---

# 7. Decisiones principales de diseño

## 7.1 Uso de `order_items` como entidad asociativa

La existencia de `order_items` es una decisión central del modelo.

Un pedido puede contener muchos productos y un producto puede aparecer en muchos pedidos. Por tanto:

```text
orders N ───── M products
```

Esta relación se transforma en dos relaciones 1:N mediante `order_items`.

Además, la línea de pedido tiene datos propios:

```text
quantity
unit_price
unit_cost
discount_percent
```

Estos valores describen la compra concreta y no pertenecen únicamente al pedido ni únicamente al producto.

---

## 7.2 Separación entre valores actuales e históricos

El modelo distingue deliberadamente entre:

```text
products.current_sale_price
products.current_cost
```

y:

```text
order_items.unit_price
order_items.unit_cost
```

Los primeros representan el estado actual del catálogo.

Los segundos representan los valores existentes cuando se realizó una compra determinada.

Esta separación evita que un cambio posterior de precio o coste modifique retrospectivamente los resultados históricos.

Por ejemplo, si un producto se vendió por 500 € y posteriormente su precio actual pasa a 450 €, el pedido antiguo debe seguir reflejando 500 €.

`unit_price` y `unit_cost` son por tanto **snapshots históricos**.

La justificación detallada respecto a las formas normales se desarrolla en [`normalizacion.md`](normalizacion.md).

---

## 7.3 Descuento a nivel de línea

`discount_percent` se almacena en `order_items`.

El descuento pertenece a una compra concreta, no al producto de forma permanente.

Un mismo producto puede venderse con diferentes descuentos en pedidos distintos.

Por eso el descuento se asocia a:

```text
(order_id, product_id)
```

y no a `products`.

---

## 7.4 Snapshot de la dirección de envío

`orders` mantiene:

```text
shipping_recipient
shipping_address_line1
shipping_postal_code
shipping_city_id
```

aunque `customers` ya disponga de una ciudad asociada.

La razón es histórica.

El destino de un pedido debe conservarse tal como era cuando se realizó el envío.

Si posteriormente el cliente cambia de ciudad, el pedido antiguo no debe modificar su destino histórico.

Por tanto, la dirección de envío es información propia del pedido.

---

## 7.5 Normalización geográfica

Aunque el pedido almacena un snapshot de la dirección, la ciudad se representa mediante:

```text
shipping_city_id
```

como FK hacia `cities`.

El país no se repite dentro de `orders`.

Se obtiene mediante:

```text
orders.shipping_city_id
→ cities.country_id
→ countries
```

Esto permite conservar la información histórica sin duplicar innecesariamente los datos del país.

---

## 7.6 `reviews` vinculada a `order_items`

Una valoración no se asocia directamente a `product_id`.

Se asocia a:

```text
order_item_id
```

De esta forma la review queda vinculada a una compra concreta.

A partir de `order_item_id` se pueden recuperar:

```text
product_id
order_id
customer_id
```

sin repetirlos en `reviews`.

Esto evita inconsistencias y permite comprobar que la valoración corresponde a un producto realmente comprado.

En los datos sintéticos las reviews se generan únicamente para líneas pertenecientes a pedidos entregados.

---

## 7.7 Separación de `payments` y `orders`

La información del pago se mantiene separada de `orders`.

Un pedido describe una operación comercial.

Un pago describe una operación financiera asociada a ese pedido.

El pago tiene atributos propios:

```text
payment_method
status
amount
payment_date
status_updated_at
external_reference
```

En la simulación actual existe un pago por pedido, pero utilizar una entidad independiente evita acoplar el estado comercial del pedido con el estado financiero.

Esta estructura permite que el modelo pueda evolucionar posteriormente hacia escenarios más complejos sin tener que rediseñar `orders`.

---

## 7.8 El total del pedido no se almacena como columna

No existe:

```text
orders.total_amount
```

porque el total comercial puede calcularse mediante:

```text
SUM(
    quantity
    × unit_price
    × (1 - discount_percent / 100)
)
+ shipping_cost
```

Los componentes originales ya se encuentran almacenados.

Mantener además un total calculado dentro de `orders` introduciría una segunda fuente de verdad que podría quedar desincronizada.

`payments.amount` sí se conserva porque representa el importe del evento de pago.

Durante la generación se comprueba que el importe del pago coincide con el total calculado del pedido.

---

## 7.9 Claves sustitutas

Las tablas utilizan identificadores numéricos como:

```text
customer_id
product_id
order_id
```

en lugar de utilizar datos de negocio como PK.

Por ejemplo, el email del cliente es único, pero no se utiliza como clave primaria.

Esto permite que atributos comerciales puedan cambiar sin modificar las relaciones existentes.

Los identificadores naturales relevantes se siguen validando como únicos.

---

## 7.10 Datos maestros frente a dominios técnicos

Se han creado tablas independientes para entidades como:

```text
countries
cities
acquisition_channels
categories
brands
```

porque son entidades reutilizables, pueden crecer y pueden incorporar nuevos atributos.

En cambio, valores pequeños y cerrados como:

```text
orders.status
payments.status
payments.payment_method
```

se representan mediante `STRING` en BigQuery y su dominio se valida en Python.

No se crean tablas adicionales para estos valores porque, dentro del alcance actual, funcionan como estados técnicos y no como entidades de negocio independientes.

---

# 8. Decisiones de tipos de datos

La implementación final utiliza los tipos de BigQuery.

| Tipo BigQuery | Uso |
|---|---|
| `INT64` | Identificadores, cantidades y stock |
| `STRING` | Textos, códigos, estados y métodos de pago |
| `NUMERIC` | Precios, costes, descuentos e importes |
| `BOOL` | Estados binarios como `is_active` |
| `DATETIME` | Fechas y horas de registro, pedidos, pagos y reviews |

Para los valores monetarios se utiliza `NUMERIC`.

Durante la generación en Python se utiliza `Decimal` para evitar errores de precisión propios de los números de coma flotante en cálculos económicos.

---

# 9. Integridad de los datos

Debido a las características de BigQuery, las PK y FK declaradas actúan como restricciones lógicas y no deben considerarse suficientes por sí solas para garantizar toda la integridad del conjunto de datos.

Por este motivo se implementa una fase de validación en Python antes de realizar la carga.

Las comprobaciones incluyen:

| Tipo de validación | Ejemplos |
|---|---|
| Claves primarias | No nulas y sin duplicados |
| Claves foráneas | Todas las FK deben apuntar a registros existentes |
| Unicidad de negocio | Email, SKU, códigos, referencias externas y combinaciones únicas |
| Rangos | Rating entre 1 y 5, descuento entre 0 y 100, cantidades positivas |
| Dominios | Estados de pedidos, estados de pagos y métodos de pago permitidos |
| Coherencia temporal | Registro anterior al pedido, envío posterior al pedido, entrega posterior al envío |
| Coherencia económica | Precios, costes y cantidades válidos |
| Pagos | Un pago por pedido y cantidad correcta |
| Reviews | Solo sobre líneas entregadas y máximo una review por línea |

La separación entre **modelo lógico** y **validación efectiva** es especialmente relevante en la implementación con BigQuery.

---

# 10. Reglas temporales

Las fechas generadas deben respetar el orden lógico de los eventos.

Para los pedidos:

```text
customer.registered_at
    <= order.order_date
    <= shipped_at
    <= delivered_at
```

cuando las fechas correspondientes existen.

Para pagos:

```text
payment_date >= order_date

status_updated_at >= payment_date
```

Para reviews:

```text
review_date >= delivered_at
```

Estas reglas garantizan que los datos sintéticos representen una secuencia de negocio coherente.

---

# 11. Reglas económicas

Se aplican reglas básicas como:

```text
current_sale_price >= 0
current_cost >= 0
stock >= 0

quantity > 0

unit_price >= 0
unit_cost >= 0

0 <= discount_percent <= 100

shipping_cost >= 0

payment.amount >= 0

1 <= rating <= 5
```

Además, la generación procura mantener relaciones económicas razonables entre precio y coste.

Los pagos se calculan utilizando los precios históricos de las líneas y el descuento correspondiente.

---

# 12. Generación de datos sintéticos

La generación se realiza en Python utilizando `Faker`.

El conjunto de datos creado incluye al menos:

| Entidad | Volumen |
|---|---:|
| Clientes | 500 |
| Productos | 70 |
| Pedidos | 2.000 |
| Líneas de pedido | 4.500 |
| Pagos | 1 por pedido |
| Reviews | Aproximadamente el 35 % de las líneas correspondientes a pedidos entregados |

Se utiliza una semilla aleatoria para favorecer la reproducibilidad.

La generación sigue el orden de las dependencias del modelo para asegurar que las FK puedan asignarse correctamente.

Por ejemplo:

```text
countries / cities
        ↓
customers
        ↓
orders
        ↓
order_items
        ↓
payments / reviews
```

---

# 13. DataFrames como capa intermedia

Cada tabla dispone de su correspondiente `DataFrame` de pandas.

Los DataFrames permiten separar:

```text
generación de los datos
```

de:

```text
persistencia en BigQuery
```

Antes de cargar los datos se realizan las validaciones sobre estos DataFrames.

Esto permite detectar errores antes de que lleguen a la base de datos.

---

# 14. Estrategia de carga en BigQuery

Las tablas se cargan respetando el orden de sus dependencias:

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

Antes de una nueva carga, las tablas pueden vaciarse en orden inverso.

Después se cargan los DataFrames utilizando el esquema ya definido en las tablas de BigQuery.

Tras finalizar la carga se compara el número de filas del DataFrame con el número de filas almacenadas en BigQuery.

De esta manera se verifica que la carga se ha realizado completamente.

---

# 15. Gestión de credenciales y configuración

La configuración del proyecto se mantiene separada del código mediante variables de entorno.

El fichero:

```text
.env
```

contiene los valores reales necesarios para la ejecución local y no debe subirse al repositorio.

El proyecto incluye:

```text
.env.example
```

como plantilla de configuración.

Las credenciales de Google Cloud tampoco se versionan.

Esta separación evita incluir información sensible directamente dentro de los notebooks.

---

# 16. Reproducibilidad

El proyecto se estructura en notebooks independientes:

```text
01_setup_bigquery.ipynb
02_generate_data.ipynb
03_queries_verification.ipynb
```

Su responsabilidad es:

| Notebook | Función |
|---|---|
| `01_setup_bigquery.ipynb` | Configuración, conexión, creación del dataset y creación del esquema |
| `02_generate_data.ipynb` | Generación, validación, carga y verificación de los datos |
| `03_queries_verification.ipynb` | Consultas analíticas sobre el modelo cargado |

El orden de ejecución esperado es:

```text
01 → 02 → 03
```

Cada notebook debe poder crear su propia conexión a BigQuery a partir de la configuración del entorno.

---

# 17. Decisiones de simplificación del alcance

El modelo busca representar correctamente el negocio requerido sin introducir entidades que no sean necesarias para el alcance actual.

Por ejemplo, los estados técnicos se mantienen como dominios controlados en lugar de crear tablas adicionales.

Del mismo modo, el total del pedido no se almacena como dato derivado.

Estas decisiones reducen la complejidad sin eliminar información necesaria para realizar análisis de ventas, clientes, catálogo, logística, pagos o valoraciones.

---

# 18. Capacidad de análisis del modelo

La estructura permite realizar consultas analíticas cruzando las distintas áreas del negocio.

Entre otras posibilidades, el modelo permite calcular:

```text
ingresos por periodo
ventas por producto
ventas por categoría
ventas por marca
margen histórico
clientes por país
clientes por canal de adquisición
pedidos por estado
tiempo medio de entrega
productos mejor valorados
tasa de valoraciones
métodos de pago utilizados
```

Esto permite comprobar que el diseño no solo es estructuralmente consistente, sino también útil para responder preguntas reales del negocio.

---

# 19. Relación con la documentación de normalización

Las decisiones recogidas en este documento están estrechamente relacionadas con la normalización del modelo.

El análisis detallado de:

```text
1NF
2NF
3NF
BCNF
4NF
5NF
```

así como las dependencias funcionales y las reglas de unicidad, se documenta en:

[`normalizacion.md`](normalizacion.md)

Ambos documentos tienen funciones diferentes:

| Documento | Objetivo |
|---|---|
| `modelo_diseno.md` | Explicar la arquitectura, entidades, relaciones y decisiones del modelo |
| `normalizacion.md` | Justificar formalmente la normalización y las dependencias entre atributos |

---

# 20. Conclusión

El modelo de SkeletIA se ha diseñado para mantener separadas las distintas responsabilidades del negocio:

```text
geografía
clientes
adquisición
catálogo
pedidos
líneas de pedido
pagos
valoraciones
```

Las principales decisiones de arquitectura buscan equilibrar integridad de los datos, conservación histórica, reducción de redundancias, claridad de las relaciones, facilidad de análisis y capacidad de evolución.

La separación entre datos actuales e históricos permite analizar correctamente pedidos antiguos incluso cuando cambian los precios, costes o datos del cliente.

La utilización de tablas maestras evita repetir información, mientras que las tablas transaccionales conservan los hechos específicos de cada operación.

Por último, las validaciones realizadas en Python complementan las restricciones lógicas del modelo en BigQuery y permiten verificar la integridad del conjunto de datos antes y después de la carga.
