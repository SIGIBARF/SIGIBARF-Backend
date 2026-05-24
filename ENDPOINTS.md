# Documentacion de Endpoints - SIGIBARF Backend

Esta documentacion describe los endpoints expuestos actualmente por el proyecto. La base de rutas esta definida en `project/urls.py`.

## Base URL

En desarrollo o produccion, anteponer el host correspondiente:

```txt
{API_BASE_URL}/api/usuarios/
{API_BASE_URL}/api/inventario/
```

Ejemplo:

```txt
https://backend.example.com/api/inventario/public/productos/
```

## Reglas Generales

- Formato de entrada y salida: JSON.
- Todas las rutas terminan en `/`.
- Autenticacion global: por defecto, todo endpoint requiere JWT, porque `REST_FRAMEWORK.DEFAULT_PERMISSION_CLASSES` usa `IsAuthenticated`.
- Excepciones publicas: los endpoints con `AllowAny` se pueden consumir sin token.
- Header para endpoints privados:

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

## Codigos de Estado Comunes

| Codigo | Significado |
|---|---|
| `200 OK` | Consulta o accion completada. |
| `201 Created` | Recurso creado. |
| `204 No Content` | Accion completada sin cuerpo de respuesta. |
| `400 Bad Request` | Datos invalidos o faltantes. |
| `401 Unauthorized` | Falta token JWT, token invalido o expirado. |
| `404 Not Found` | Recurso inexistente. |
| `405 Method Not Allowed` | Metodo HTTP no soportado por esa ruta. |

## Autenticacion y Usuarios

Base: `/api/usuarios/`

### Modelo de Usuario en Respuestas

Este es el formato usado por `UsuarioSerializer`:

| Campo | Tipo | Escritura | Descripcion |
|---|---:|---|---|
| `id` | integer | Solo lectura | ID del usuario. |
| `correo` | email string | Solo lectura en perfil | Correo unico. |
| `nombre` | string, max 100 | Editable en perfil | Nombre. |
| `apellido` | string, max 100 | Editable en perfil | Apellido. |
| `telefono` | string, max 20 | Editable en perfil | Puede estar vacio. |
| `direccion` | string, max 255 | Editable en perfil | Puede estar vacio. |
| `rol` | string | Solo lectura | Nombre del rol: `Cliente` o `Administrador`. |
| `is_perfil_completo` | boolean | Calculado | En `PATCH/PUT /me/`, queda `true` solo si `telefono` y `direccion` no estan vacios. |
| `is_active` | boolean | Solo lectura | Estado de la cuenta. |
| `created_at` | datetime | Solo lectura | Fecha de creacion. |
| `updated_at` | datetime | Solo lectura | Ultima actualizacion. |

### `GET /api/usuarios/health/`

Publico. Sirve para verificar que el backend responde.

Respuesta `200`:

```json
{
  "status": "ok"
}
```

### `POST /api/usuarios/auth/register/`

Publico. Registra un usuario cliente.

Body:

| Campo | Tipo | Requerido | Validaciones |
|---|---:|---:|---|
| `correo` | email string | Si | Debe ser unico, comparado sin distinguir mayusculas/minusculas. |
| `password` | string | Si | Minimo 8 caracteres y validadores de password de Django. |
| `password_confirm` | string | Si | Debe coincidir con `password`. |
| `nombre` | string, max 100 | Si | No vacio. |
| `apellido` | string, max 100 | Si | No vacio. |
| `telefono` | string, max 20 | No | Puede enviarse como `""`. Default `""`. |
| `direccion` | string, max 255 | No | Puede enviarse como `""`. Default `""`. |

Ejemplo:

```json
{
  "correo": "cliente@example.com",
  "password": "PasswordSeguro123",
  "password_confirm": "PasswordSeguro123",
  "nombre": "Ana",
  "apellido": "Perez",
  "telefono": "3001234567",
  "direccion": "Calle 1 # 2-3"
}
```

Respuesta `201`:

```json
{
  "detail": "Cuenta creada correctamente. Inicia sesion con tu correo y contrasena.",
  "user": {
    "id": 1,
    "correo": "cliente@example.com",
    "nombre": "Ana",
    "apellido": "Perez",
    "telefono": "3001234567",
    "direccion": "Calle 1 # 2-3",
    "rol": "Cliente",
    "is_perfil_completo": false,
    "is_active": true,
    "created_at": "2026-05-24T00:00:00Z",
    "updated_at": "2026-05-24T00:00:00Z"
  }
}
```

Errores comunes `400`:

```json
{"correo": ["Ya existe una cuenta con este correo."]}
```

```json
{"password_confirm": "Las contrasenas no coinciden."}
```

### `POST /api/usuarios/auth/login/`

Publico. Inicia sesion con correo y password.

Body:

| Campo | Tipo | Requerido |
|---|---:|---:|
| `correo` | email string | Si |
| `password` | string | Si |

Respuesta `200`:

```json
{
  "tokens": {
    "refresh": "<refresh_token>",
    "access": "<access_token>"
  },
  "user": {
    "id": 1,
    "correo": "cliente@example.com",
    "nombre": "Ana",
    "apellido": "Perez",
    "telefono": "",
    "direccion": "",
    "rol": "Cliente",
    "is_perfil_completo": false,
    "is_active": true,
    "created_at": "2026-05-24T00:00:00Z",
    "updated_at": "2026-05-24T00:00:00Z"
  }
}
```

Notas:

- El `access` dura 1 hora.
- El `refresh` dura 7 dias.
- El token incluye el claim `rol` si el usuario tiene rol.

Errores comunes `400`:

```json
["Correo o contrasena incorrectos."]
```

```json
["La cuenta esta inactiva."]
```

### `POST /api/usuarios/auth/google/`

Publico. Login o registro por Google.

Body:

| Campo | Tipo | Requerido | Descripcion |
|---|---:|---:|---|
| `id_token` | string | Si | Token de Google Identity Services. |

Respuesta `200`: igual a login, con `tokens` y `user`.

Restricciones:

- `GOOGLE_OAUTH_CLIENT_ID` debe estar configurado en el servidor.
- Google debe devolver correo.
- El correo de Google debe estar verificado.
- Si el correo ya existe e `is_active=false`, se rechaza.
- Si el correo no existe, se crea usuario con rol `Cliente` y password inutilizable.

Errores comunes `400`:

```json
["Token de Google invalido o expirado."]
```

```json
["Inicio con Google no esta configurado en el servidor."]
```

### `POST /api/usuarios/auth/refresh/`

Publico. Renueva tokens usando refresh token.

Body:

```json
{
  "refresh": "<refresh_token>"
}
```

Respuesta `200` tipica de SimpleJWT:

```json
{
  "access": "<new_access_token>",
  "refresh": "<new_refresh_token>"
}
```

Notas:

- `ROTATE_REFRESH_TOKENS=True`, por eso puede venir un refresh nuevo.
- `BLACKLIST_AFTER_ROTATION=True`, el refresh anterior queda revocado.

### `POST /api/usuarios/auth/logout/`

Privado. Requiere JWT. Revoca un refresh token.

Body:

```json
{
  "refresh": "<refresh_token>"
}
```

Respuesta `204`: sin cuerpo.

Errores:

```json
{"detail": "Se requiere el campo refresh."}
```

```json
{"detail": "Refresh token invalido o ya revocado."}
```

### `GET /api/usuarios/me/`

Privado. Devuelve el usuario autenticado.

Respuesta `200`: `UsuarioSerializer`.

### `PATCH /api/usuarios/me/`

Privado. Actualiza parcialmente el perfil.

Campos editables:

| Campo | Tipo | Requerido en PATCH | Notas |
|---|---:|---:|---|
| `nombre` | string | No | Max 100. |
| `apellido` | string | No | Max 100. |
| `telefono` | string | No | Max 20, puede ser `""`. |
| `direccion` | string | No | Max 255, puede ser `""`. |
| `is_perfil_completo` | boolean | No recomendado | El backend lo recalcula despues de guardar. |

No editables desde este endpoint: `id`, `correo`, `rol`, `is_active`, `created_at`, `updated_at`.

Ejemplo:

```json
{
  "telefono": "3001234567",
  "direccion": "Calle 1 # 2-3"
}
```

Respuesta `200`: usuario actualizado.

### `PUT /api/usuarios/me/`

Privado. Actualizacion completa del perfil. Debe enviar los campos requeridos por el serializer para una actualizacion completa. En frontend se recomienda usar `PATCH`.

### `POST /api/usuarios/auth/change-password/`

Privado. Cambia la contrasena del usuario autenticado.

Body:

| Campo | Tipo | Requerido | Validaciones |
|---|---:|---:|---|
| `current_password` | string | Si | Debe coincidir con la actual. |
| `new_password` | string | Si | Minimo 8 y validadores de Django. |
| `new_password_confirm` | string | Si | Debe coincidir con `new_password`. |

Respuesta `200`:

```json
{
  "detail": "Contrasena actualizada correctamente."
}
```

Errores comunes:

```json
{"current_password": "La contrasena actual no es correcta."}
```

```json
{"new_password_confirm": "Las contrasenas no coinciden."}
```

### `POST /api/usuarios/auth/password-reset/`

Publico. Solicita correo de restablecimiento.

Body:

```json
{
  "correo": "cliente@example.com"
}
```

Respuesta `200`, exista o no el correo:

```json
{
  "detail": "Si el correo existe en la plataforma, se envio el enlace de restablecimiento."
}
```

Notas:

- Si `RESEND_API_KEY` no esta configurada, el backend no envia correo real y registra/imprime el contenido.
- El enlace enviado apunta a `{FRONTEND_URL}/reset-password?uid=<uidb64>&token=<token>`.

### `GET /api/usuarios/auth/password-reset/confirm/<uidb64>/<token>/`

Publico. Valida si el token de restablecimiento sigue vigente.

Respuesta `200`:

```json
{"detail": "Token valido."}
```

Respuesta `400`:

```json
{"detail": "Token invalido o expirado."}
```

### `POST /api/usuarios/auth/password-reset/confirm/<uidb64>/<token>/`

Publico. Restablece contrasena usando token valido.

Body:

| Campo | Tipo | Requerido | Validaciones |
|---|---:|---:|---|
| `new_password` | string | Si | Minimo 8 y validadores de Django. |
| `new_password_confirm` | string | Si | Debe coincidir. |

Respuesta `200`:

```json
{
  "detail": "Contrasena restablecida correctamente."
}
```

## Inventario

Base: `/api/inventario/`

### Uso Publico vs Privado

Para la tienda publica, usar solo:

- `GET /api/inventario/public/productos/`
- `GET /api/inventario/public/ingredientes/`
- `GET /api/inventario/public/producto-ingredientes/`

Estos no requieren JWT.

Para panel administrativo o frontend autenticado, usar los endpoints privados del router:

- `/api/inventario/ingredientes/`
- `/api/inventario/productos/`
- `/api/inventario/producto-ingredientes/`
- `/api/inventario/movimientos-ingrediente/`
- `/api/inventario/movimientos-producto/`
- `/api/inventario/producciones/`

Todos los privados requieren JWT por la configuracion global. Actualmente no hay permiso por rol aplicado en estas vistas; cualquier usuario autenticado podria llamar estos endpoints si tiene token valido. Si el frontend tiene panel admin, debe filtrar por `user.rol`, pero la restriccion fuerte deberia agregarse tambien en backend.

## Campos de Inventario

### Ingrediente

| Campo | Tipo | Requerido al crear | Publico | Validaciones / Notas |
|---|---:|---:|---:|---|
| `id` | integer | No | Si | Autogenerado. |
| `nombre` | string, max 100 | Si | Si | No puede ser vacio. |
| `proveedor` | string, max 100 | Si | No en endpoint publico | No puede ser vacio. |
| `stock_actual` | decimal string, 10 digitos, 2 decimales | Si | Si | Debe ser `> 0` por serializer. |
| `stock_minimo` | decimal string, 10 digitos, 2 decimales | Si | Si | Debe ser `> 0` por serializer. |
| `unidad_medida` | string | Si | Si | Opciones: `kg`, `g`, `l`, `ml`. |

### Producto

| Campo | Tipo | Requerido al crear | Publico | Validaciones / Notas |
|---|---:|---:|---:|---|
| `id` | integer | No | Si | Autogenerado. |
| `nombre` | string, max 100 | Si | Si | No puede ser vacio. |
| `precio` | decimal string, 10 digitos, 2 decimales | Si | Si | Debe ser `> 0`. |
| `stock_actual` | integer | Si | Si | Minimo `0`. |
| `stock_minimo` | integer | Si | Si | Minimo `0`. |
| `inhabilitado` | boolean | No | Si | Default `false`. El endpoint publico de productos solo devuelve registros con `inhabilitado=false`. |
| `ingredientes` | array de IDs | No | Si | ManyToMany through `ProductoIngrediente`; normalmente administrar desde `producto-ingredientes`. |

### ProductoIngrediente

Relacion entre producto e ingrediente.

| Campo | Tipo | Requerido al crear | Publico | Validaciones / Notas |
|---|---:|---:|---:|---|
| `id` | integer | No | Si | Autogenerado. |
| `id_producto` | integer | Si | Si | ID de producto existente. |
| `id_ingrediente` | integer | Si | Si | ID de ingrediente existente. |
| `cantidad_ingrediente` | decimal string, 10 digitos, 2 decimales | Si | Si | Debe ser `> 0`. Cantidad de ingrediente requerida por unidad producida. |
| `porcentaje_ingrediente` | decimal string, 5 digitos, 2 decimales | Si | Si | Debe ser `> 0` y `<= 100`. |

### Produccion

| Campo | Tipo | Requerido al crear | Validaciones / Notas |
|---|---:|---:|---|
| `id` | integer | No | Autogenerado. |
| `id_producto` | integer | Si | Producto existente. |
| `cantidad_producida` | integer | Si | Minimo `1`. |
| `fecha` | date/datetime | No | Solo lectura; se genera automaticamente. El serializer actual la devuelve como fecha. |

Al crear una produccion con `POST /api/inventario/producciones/`, el backend:

1. Bloquea el producto con `select_for_update`.
2. Valida stock suficiente de cada ingrediente.
3. Descuenta ingredientes segun `cantidad_ingrediente * cantidad_producida`.
4. Crea movimientos de ingrediente tipo `SALIDA`.
5. Aumenta `Producto.stock_actual`.
6. Crea movimiento de producto tipo `ENTRADA`.
7. Crea el registro de produccion.

### MovimientoIngrediente

| Campo | Tipo | Requerido al crear | Validaciones / Notas |
|---|---:|---:|---|
| `id` | integer | No | Autogenerado. |
| `id_ingrediente` | integer | Si | Ingrediente existente. |
| `tipo_movimiento` | string | Si | Opciones: `ENTRADA`, `SALIDA`, `AJUSTE`. |
| `stock_anterior` | decimal string | No | Solo lectura en serializer. |
| `stock_posterior` | decimal string | No | Solo lectura en serializer. |
| `cantidad` | decimal string | Si | Debe ser `> 0`. |
| `fecha` | date/datetime | No | Solo lectura; se genera automaticamente. |
| `comentarios` | string/null | No | Texto opcional. |

Advertencia: aunque existe ViewSet de movimientos, el serializer marca stocks como solo lectura y no hay servicio que calcule `stock_anterior`/`stock_posterior` en creacion directa. Para movimientos generados por produccion, usar `POST /api/inventario/producciones/`.

### MovimientoProducto

| Campo | Tipo | Requerido al crear | Validaciones / Notas |
|---|---:|---:|---|
| `id` | integer | No | Autogenerado. |
| `id_producto` | integer | Si | Producto existente. |
| `tipo_movimiento` | string | Si | Opciones: `ENTRADA`, `SALIDA`, `AJUSTE`. |
| `stock_anterior` | integer | No | Solo lectura en serializer. |
| `stock_posterior` | integer | No | Solo lectura en serializer. |
| `cantidad` | integer | Si | Minimo `1`. |
| `fecha` | date/datetime | No | Solo lectura; se genera automaticamente. |
| `comentarios` | string/null | No | Texto opcional. |

Advertencia: igual que `MovimientoIngrediente`, la creacion directa no calcula stocks. Para entrada por produccion, usar `POST /api/inventario/producciones/`.

## Endpoints Publicos de Tienda

### `GET /api/inventario/public/productos/`

Publico. Lista productos habilitados. Excluye productos con `inhabilitado=true`.

Respuesta `200`:

```json
[
  {
    "id": 1,
    "nombre": "Producto demo",
    "precio": "12000.00",
    "stock_actual": 10,
    "stock_minimo": 2,
    "inhabilitado": false,
    "ingredientes": [1, 2]
  }
]
```

Notas para frontend:

- Este endpoint no requiere token.
- Devuelve los mismos campos que el serializer privado de producto.
- Solo devuelve productos con `inhabilitado=false`; los productos inhabilitados no aparecen en la respuesta.

### `GET /api/inventario/public/ingredientes/`

Publico. Lista ingredientes sin exponer proveedor.

Respuesta `200`:

```json
[
  {
    "id": 1,
    "nombre": "Azucar",
    "stock_actual": "100.00",
    "stock_minimo": "10.00",
    "unidad_medida": "kg"
  }
]
```

Campo oculto solo aqui:

- `proveedor`

### `GET /api/inventario/public/producto-ingredientes/`

Publico. Lista relaciones producto-ingrediente.

Respuesta `200`:

```json
[
  {
    "id": 1,
    "cantidad_ingrediente": "2.50",
    "porcentaje_ingrediente": "10.00",
    "id_producto": 1,
    "id_ingrediente": 1
  }
]
```

Uso recomendado:

- Combinar con `public/productos/` y `public/ingredientes/` si la tienda necesita mostrar composicion o detalles del producto.
- La respuesta trae IDs, no objetos anidados.

## Endpoints Privados de Inventario - Router

Los siguientes endpoints son generados por `DefaultRouter` para cada recurso. Todos requieren JWT.

### Patron de rutas ViewSet

Para cada recurso:

| Metodo | Ruta | Descripcion |
|---|---|---|
| `GET` | `/api/inventario/<recurso>/` | Listar. |
| `POST` | `/api/inventario/<recurso>/` | Crear. |
| `GET` | `/api/inventario/<recurso>/<id>/` | Obtener detalle. |
| `PUT` | `/api/inventario/<recurso>/<id>/` | Reemplazar completo. |
| `PATCH` | `/api/inventario/<recurso>/<id>/` | Actualizar parcial. |
| `DELETE` | `/api/inventario/<recurso>/<id>/` | Eliminar. |

Recursos disponibles:

- `ingredientes`
- `productos`
- `producto-ingredientes`
- `movimientos-ingrediente`
- `movimientos-producto`

### Ingredientes Privado

Base: `/api/inventario/ingredientes/`

#### `GET /api/inventario/ingredientes/`

Lista todos los ingredientes, incluyendo proveedor.

#### `POST /api/inventario/ingredientes/`

Body:

```json
{
  "nombre": "Azucar",
  "proveedor": "Proveedor A",
  "stock_actual": "100.00",
  "stock_minimo": "10.00",
  "unidad_medida": "kg"
}
```

Validaciones:

- `nombre` y `proveedor` no pueden ser vacios.
- `stock_actual` y `stock_minimo` deben ser decimales `> 0`.
- `unidad_medida`: `kg`, `g`, `l`, `ml`.

#### `PATCH /api/inventario/ingredientes/<id>/`

Actualiza parcialmente cualquier campo enviado.

### Productos Privado

Base: `/api/inventario/productos/`

#### `GET /api/inventario/productos/`

Lista todos los productos.

#### `POST /api/inventario/productos/`

Body:

```json
{
  "nombre": "Producto demo",
  "precio": "12000.00",
  "stock_actual": 10,
  "stock_minimo": 2,
  "inhabilitado": false
}
```

Tambien puede recibir `ingredientes` como array de IDs si se quiere manejar el ManyToMany directamente, aunque la ruta recomendada para cantidades y porcentajes es `producto-ingredientes`.

Validaciones:

- `nombre` no puede ser vacio.
- `precio` debe ser decimal `> 0`.
- `stock_actual` y `stock_minimo` deben ser enteros `>= 0`.
- `inhabilitado` es opcional; default `false`.

#### `PATCH /api/inventario/productos/<id>/`

Actualiza parcialmente un producto. Ejemplo para inhabilitar:

```json
{
  "inhabilitado": true
}
```

### Producto-Ingredientes Privado

Base: `/api/inventario/producto-ingredientes/`

#### `GET /api/inventario/producto-ingredientes/`

Lista relaciones producto-ingrediente.

#### `POST /api/inventario/producto-ingredientes/`

Body:

```json
{
  "id_producto": 1,
  "id_ingrediente": 1,
  "cantidad_ingrediente": "2.50",
  "porcentaje_ingrediente": "10.00"
}
```

Validaciones:

- `cantidad_ingrediente` debe ser `> 0`.
- `porcentaje_ingrediente` debe ser `> 0` y `<= 100`.
- `id_producto` e `id_ingrediente` deben existir.

### Movimientos de Ingrediente Privado

Base: `/api/inventario/movimientos-ingrediente/`

#### `GET /api/inventario/movimientos-ingrediente/`

Lista movimientos.

#### `POST /api/inventario/movimientos-ingrediente/`

No recomendado para flujo de produccion. Usar `POST /api/inventario/producciones/`.

Body teorico:

```json
{
  "id_ingrediente": 1,
  "tipo_movimiento": "SALIDA",
  "cantidad": "2.50",
  "comentarios": "Ajuste manual"
}
```

Limitacion actual:

- `stock_anterior` y `stock_posterior` son solo lectura en serializer, pero obligatorios en base de datos. La creacion directa puede fallar si no se implementa servicio de ajuste manual.

### Movimientos de Producto Privado

Base: `/api/inventario/movimientos-producto/`

#### `GET /api/inventario/movimientos-producto/`

Lista movimientos.

#### `POST /api/inventario/movimientos-producto/`

No recomendado para flujo de produccion. Usar `POST /api/inventario/producciones/`.

Body teorico:

```json
{
  "id_producto": 1,
  "tipo_movimiento": "ENTRADA",
  "cantidad": 5,
  "comentarios": "Ajuste manual"
}
```

Limitacion actual:

- `stock_anterior` y `stock_posterior` son solo lectura en serializer, pero obligatorios en base de datos. La creacion directa puede fallar si no se implementa servicio de ajuste manual.

## Producciones

### `GET /api/inventario/producciones/`

Privado. Lista producciones ordenadas por `fecha` descendente.

Respuesta `200`:

```json
[
  {
    "id": 1,
    "cantidad_producida": 10,
    "fecha": "2026-05-24",
    "id_producto": 1
  }
]
```

### `POST /api/inventario/producciones/`

Privado. Crea una produccion y actualiza inventario en una transaccion.

Body:

```json
{
  "id_producto": 1,
  "cantidad_producida": 10
}
```

Validaciones:

- `id_producto` es requerido.
- `cantidad_producida` es requerida.
- `cantidad_producida` debe ser entero.
- `cantidad_producida` debe ser mayor que `0`.
- El producto debe existir.
- Debe haber stock suficiente de ingredientes segun las relaciones `ProductoIngrediente`.

Respuesta `201`:

```json
{
  "id": 1,
  "cantidad_producida": 10,
  "fecha": "2026-05-24",
  "id_producto": 1
}
```

Errores:

```json
{"detail": "id_producto y cantidad_producida son requeridos."}
```

```json
{"detail": "cantidad_producida debe ser un entero."}
```

```json
{"detail": "Producto no encontrado."}
```

```json
{
  "detail": "Ingrediente \"Azucar\" (id=1) no tiene stock suficiente: requerido 100.00, disponible 50.00"
}
```

Efectos secundarios:

- Descuenta `Ingrediente.stock_actual`.
- Crea `MovimientoIngrediente` tipo `SALIDA`.
- Incrementa `Producto.stock_actual`.
- Crea `MovimientoProducto` tipo `ENTRADA`.
- Crea `Produccion`.

## Panel Admin de Django

Ruta web:

```txt
/admin/
```

No es API JSON. Es el panel administrativo de Django.

Modelos registrados:

- Ingredientes
- Productos
- Productos_Ingredientes
- Producciones
- Movimientos_Ingredientes
- Movimientos_Productos
- Usuarios
- Roles

Nota importante de producciones:

- Crear una `Produccion` desde el admin ejecuta el mismo servicio que `POST /api/inventario/producciones/`.
- Por tanto descuenta ingredientes, aumenta stock del producto y crea movimientos.
- Si no hay stock suficiente, el formulario muestra error de validacion.

## Apps con Modelos pero sin API Expuesta

Estas apps existen en `INSTALLED_APPS`, pero actualmente no estan incluidas en `project/urls.py` o no tienen endpoints implementados:

### Ventas

Modelos:

- `CarritoDeCompras`
- `Pedido`
- `PedidoProducto`

No hay `/api/ventas/` montado actualmente.

### Creditos

Modelos:

- `Credito`
- `CuotaCredito`

No hay `/api/creditos/` montado actualmente.

### Notificaciones

Modelo:

- `Notificacion`

No hay `/api/notificaciones/` montado actualmente.

## Recomendaciones para Frontend

### Tienda Publica

Usar:

- `GET /api/inventario/public/productos/`
- `GET /api/inventario/public/ingredientes/`
- `GET /api/inventario/public/producto-ingredientes/`
- `POST /api/usuarios/auth/register/`
- `POST /api/usuarios/auth/login/`
- `POST /api/usuarios/auth/google/`
- `POST /api/usuarios/auth/password-reset/`
- `GET/POST /api/usuarios/auth/password-reset/confirm/<uidb64>/<token>/`

No enviar JWT en endpoints publicos; no lo necesitan.

### Cliente Autenticado

Usar:

- `GET /api/usuarios/me/`
- `PATCH /api/usuarios/me/`
- `POST /api/usuarios/auth/change-password/`
- `POST /api/usuarios/auth/logout/`
- `POST /api/usuarios/auth/refresh/`

### Panel Administrativo Frontend

Usar endpoints privados de inventario con JWT:

- CRUD de ingredientes.
- CRUD de productos.
- CRUD de producto-ingredientes.
- `POST /api/inventario/producciones/` para producir y mover stock correctamente.
- `GET /api/inventario/movimientos-ingrediente/` y `GET /api/inventario/movimientos-producto/` para historicos.

Evitar:

- Crear movimientos manualmente hasta que exista un servicio backend para calcular stocks.
- Usar los endpoints publicos para administracion, porque ocultan o simplifican informacion.

## Pendientes Tecnicos Detectados

Estos puntos no bloquean el consumo actual, pero son importantes para planificacion:

- Los endpoints privados de inventario no aplican permisos por rol; solo exigen autenticacion.
- No hay API implementada para ventas/carrito/pedidos.
- No hay API implementada para creditos.
- No hay API implementada para notificaciones.
- Los endpoints de movimientos permiten rutas de creacion por `ModelViewSet`, pero no tienen logica de actualizacion de stock fuera de produccion.
- Los endpoints de listado no tienen paginacion, filtros ni busqueda configurados.
