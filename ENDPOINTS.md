# Documentación de Endpoints - SIGIBARF Backend

Este archivo documenta las rutas expuestas por el backend Django/DRF. La fuente de verdad de montaje de rutas está en `project/urls.py`.

## Base URL

Rutas montadas actualmente:

```txt
{API_BASE_URL}/api/usuarios/
{API_BASE_URL}/api/inventario/
{API_BASE_URL}/api/notificaciones/
```

Ejemplo:

```txt
https://backend.example.com/api/inventario/public/productos/
```

## Reglas Generales

- Formato de entrada y salida: JSON.
- Todas las rutas terminan en `/`.
- Autenticación API: JWT por header `Authorization: Bearer <access_token>`.
- Los endpoints públicos declaran `AllowAny` y no requieren token.
- Los endpoints privados de inventario usan el permiso global `IsAdministrador`.
- `IsAdministrador` permite usuarios con rol de negocio `Administrador`; también permite `is_staff` o `is_superuser` por implementación de permisos.
- Algunos endpoints de usuario son privados pero solo requieren usuario autenticado, no rol `Administrador`.
- Los listados no tienen paginación, búsqueda ni filtros configurados, salvo endpoints específicos documentados.
- Las fechas se serializan como ISO 8601. El proyecto usa `USE_TZ=True` y `TIME_ZONE="UTC"` en `settings.py`.

Header recomendado para endpoints privados:

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

## Códigos de Estado Comunes

| Código | Significado |
|---|---|
| `200 OK` | Consulta o acción completada. |
| `201 Created` | Recurso creado. |
| `204 No Content` | Acción completada sin cuerpo de respuesta. |
| `400 Bad Request` | Datos inválidos o faltantes. |
| `401 Unauthorized` | Falta token JWT, token inválido o token expirado. |
| `403 Forbidden` | Usuario autenticado sin permiso para la ruta. |
| `404 Not Found` | Recurso inexistente o no visible para el usuario autenticado. |
| `405 Method Not Allowed` | Método HTTP no soportado por esa ruta. |

## Resumen de Rutas

### Usuarios

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| `GET` | `/api/usuarios/health/` | Público | Health check. |
| `POST` | `/api/usuarios/auth/register/` | Público | Registro de cliente. |
| `POST` | `/api/usuarios/auth/login/` | Público | Login con correo y contraseña. |
| `POST` | `/api/usuarios/auth/google/` | Público | Login/registro con Google. |
| `POST` | `/api/usuarios/auth/refresh/` | Público | Renovar token. |
| `POST` | `/api/usuarios/auth/password-reset/` | Público | Solicitar restablecimiento de contraseña. |
| `GET` | `/api/usuarios/auth/password-reset/confirm/<uidb64>/<token>/` | Público | Validar token de restablecimiento. |
| `POST` | `/api/usuarios/auth/password-reset/confirm/<uidb64>/<token>/` | Público | Restablecer contraseña. |
| `POST` | `/api/usuarios/auth/logout/` | Autenticado | Revocar refresh token. |
| `GET` | `/api/usuarios/me/` | Autenticado | Obtener perfil propio. |
| `PUT` | `/api/usuarios/me/` | Autenticado | Actualizar perfil completo. |
| `PATCH` | `/api/usuarios/me/` | Autenticado | Actualizar perfil parcial. |
| `POST` | `/api/usuarios/auth/change-password/` | Autenticado | Cambiar contraseña. |
| `GET` | `/api/usuarios/clientes/` | Admin | Listar usuarios con rol Cliente. |
| `GET` | `/api/usuarios/clientes/<id>/` | Admin | Detalle de un cliente. |

### Inventario

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| `GET` | `/api/inventario/public/productos/` | Público | Productos habilitados para tienda. |
| `GET` | `/api/inventario/public/ingredientes/` | Público | Ingredientes sin proveedor. |
| `GET` | `/api/inventario/public/producto-ingredientes/` | Público | Relaciones producto-ingrediente. |
| `GET/POST` | `/api/inventario/ingredientes/` | Admin | Listar o crear ingredientes. |
| `GET/PUT/PATCH/DELETE` | `/api/inventario/ingredientes/<id>/` | Admin | Detalle, actualización o eliminación. |
| `GET/POST` | `/api/inventario/productos/` | Admin | Listar o crear productos. |
| `GET/PUT/PATCH/DELETE` | `/api/inventario/productos/<id>/` | Admin | Detalle, actualización o eliminación. |
| `GET/POST` | `/api/inventario/producto-ingredientes/` | Admin | Listar o crear relaciones. |
| `GET/PUT/PATCH/DELETE` | `/api/inventario/producto-ingredientes/<id>/` | Admin | Detalle, actualización o eliminación. |
| `GET/POST` | `/api/inventario/movimientos-ingrediente/` | Admin | Listar historial o crear movimiento. |
| `GET` | `/api/inventario/movimientos-ingrediente/<id>/` | Admin | Detalle de movimiento. |
| `GET/POST` | `/api/inventario/movimientos-producto/` | Admin | Listar historial o crear movimiento. |
| `GET` | `/api/inventario/movimientos-producto/<id>/` | Admin | Detalle de movimiento. |
| `GET` | `/api/inventario/producciones/` | Admin | Listar producciones. |
| `POST` | `/api/inventario/producciones/` | Admin | Crear producción y mover stock. |
| `GET` | `/api/inventario/producciones/proximas-a-vencer/` | Admin | Lotes de producción que vencen entre hoy y un mes calendario. |

### Notificaciones

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| `GET` | `/api/notificaciones/` | Autenticado, visible para Admin | Lista notificaciones activas no leídas. |
| `PATCH` | `/api/notificaciones/<id>/resolve/` | Autenticado, visible para Admin | Marca una notificación como leída. |

## Autenticación y Usuarios

Base: `/api/usuarios/`

### Modelo de Usuario en Respuestas

Formato usado por `UsuarioSerializer`:

| Campo | Tipo | Escritura | Descripción |
|---|---:|---|---|
| `id` | integer | Solo lectura | ID del usuario. |
| `correo` | email string | Solo lectura | Correo único. |
| `nombre` | string, max 100 | Editable | Nombre. |
| `apellido` | string, max 100 | Editable | Apellido. |
| `telefono` | string, max 20 | Editable | Puede estar vacío. |
| `direccion` | string, max 255 | Editable | Puede estar vacío. |
| `rol` | string | Solo lectura | Nombre del rol: `Cliente` o `Administrador`. |
| `is_perfil_completo` | boolean | Recalculado por backend | Queda `true` solo si `telefono` y `direccion` tienen contenido. |
| `is_active` | boolean | Solo lectura | Estado de la cuenta. |
| `created_at` | datetime | Solo lectura | Fecha de creación. |
| `updated_at` | datetime | Solo lectura | Última actualización. |

### `GET /api/usuarios/health/`

Público. Verifica que el backend responde.

Respuesta `200`:

```json
{
  "status": "ok"
}
```

### `POST /api/usuarios/auth/register/`

Público. Registra un usuario con rol `Cliente`.

Body:

| Campo | Tipo | Requerido | Validaciones |
|---|---:|---:|---|
| `correo` | email string | Sí | Debe ser único, comparado sin distinguir mayúsculas/minúsculas. |
| `password` | string | Sí | Mínimo 8 caracteres y validadores de Django. |
| `password_confirm` | string | Sí | Debe coincidir con `password`. |
| `nombre` | string, max 100 | Sí | No vacío. |
| `apellido` | string, max 100 | Sí | No vacío. |
| `telefono` | string, max 20 | No | Puede ser `""`. Default `""`. |
| `direccion` | string, max 255 | No | Puede ser `""`. Default `""`. |

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
  "detail": "Cuenta creada correctamente. Inicia sesión con tu correo y contraseña.",
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

Errores comunes:

```json
{"correo": ["Ya existe una cuenta con este correo."]}
```

```json
{"password_confirm": "Las contraseñas no coinciden."}
```

### `POST /api/usuarios/auth/login/`

Público. Inicia sesión con correo y contraseña.

Body:

| Campo | Tipo | Requerido |
|---|---:|---:|
| `correo` | email string | Sí |
| `password` | string | Sí |

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
- El `refresh` dura 7 días.
- El token incluye el claim `rol` cuando el usuario tiene rol asignado.

Errores comunes:

```json
["Correo o contraseña incorrectos."]
```

```json
["La cuenta está inactiva."]
```

### `POST /api/usuarios/auth/google/`

Público. Hace login o registro con Google Identity Services.

Body:

| Campo | Tipo | Requerido | Descripción |
|---|---:|---:|---|
| `id_token` | string | Sí | Token emitido por Google. |

Respuesta `200`: igual a login, con `tokens` y `user`.

Restricciones:

- `GOOGLE_OAUTH_CLIENT_ID` debe estar configurado en el servidor.
- Google debe devolver correo.
- El correo de Google debe estar verificado.
- Si el correo ya existe con `is_active=false`, se rechaza.
- Si el correo no existe, se crea usuario con rol `Cliente` y password inutilizable.

Errores comunes:

```json
["Token de Google inválido o expirado."]
```

```json
["Inicio con Google no está configurado en el servidor."]
```

### `POST /api/usuarios/auth/refresh/`

Público. Renueva tokens usando un refresh token.

Body:

```json
{
  "refresh": "<refresh_token>"
}
```

Respuesta `200` típica de SimpleJWT:

```json
{
  "access": "<new_access_token>",
  "refresh": "<new_refresh_token>"
}
```

Notas:

- `ROTATE_REFRESH_TOKENS=True`; puede devolver un refresh nuevo.
- `BLACKLIST_AFTER_ROTATION=True`; el refresh anterior queda revocado.

### `POST /api/usuarios/auth/logout/`

Privado. Requiere cualquier usuario autenticado. Revoca un refresh token.

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
{"detail": "Refresh token inválido o ya revocado."}
```

### `GET /api/usuarios/me/`

Privado. Requiere cualquier usuario autenticado. Devuelve el usuario autenticado.

Respuesta `200`: objeto `UsuarioSerializer`.

### `PATCH /api/usuarios/me/`

Privado. Requiere cualquier usuario autenticado. Actualiza parcialmente el perfil.

Campos editables:

| Campo | Tipo | Requerido en PATCH | Notas |
|---|---:|---:|---|
| `nombre` | string | No | Máximo 100. |
| `apellido` | string | No | Máximo 100. |
| `telefono` | string | No | Máximo 20, puede ser `""`. |
| `direccion` | string | No | Máximo 255, puede ser `""`. |
| `is_perfil_completo` | boolean | No recomendado | El backend lo recalcula después de guardar. |

Ejemplo:

```json
{
  "telefono": "3001234567",
  "direccion": "Calle 1 # 2-3"
}
```

Respuesta `200`: usuario actualizado.

### `PUT /api/usuarios/me/`

Privado. Requiere cualquier usuario autenticado. Actualización completa del perfil. En frontend se recomienda usar `PATCH`.

### `POST /api/usuarios/auth/change-password/`

Privado. Requiere cualquier usuario autenticado. Cambia la contraseña del usuario autenticado.

Body:

| Campo | Tipo | Requerido | Validaciones |
|---|---:|---:|---|
| `current_password` | string | Sí | Debe coincidir con la actual. |
| `new_password` | string | Sí | Mínimo 8 y validadores de Django. |
| `new_password_confirm` | string | Sí | Debe coincidir con `new_password`. |

Respuesta `200`:

```json
{
  "detail": "Contraseña actualizada correctamente."
}
```

Errores comunes:

```json
{"current_password": "La contraseña actual no es correcta."}
```

```json
{"new_password_confirm": "Las contraseñas no coinciden."}
```

### `POST /api/usuarios/auth/password-reset/`

Público. Solicita correo de restablecimiento.

Body:

```json
{
  "correo": "cliente@example.com"
}
```

Respuesta `200`, exista o no el correo:

```json
{
  "detail": "Si el correo existe en la plataforma, se envió el enlace de restablecimiento."
}
```

Notas:

- Si `RESEND_API_KEY` no está configurada, el backend no envía correo real y registra/imprime el contenido.
- El enlace enviado apunta a `{FRONTEND_URL}/auth/reset-password?uid=<uidb64>&token=<token>`.

### `GET /api/usuarios/auth/password-reset/confirm/<uidb64>/<token>/`

Público. Valida si el token de restablecimiento sigue vigente.

Respuesta `200`:

```json
{"detail": "Token válido."}
```

Respuesta `400`:

```json
{"detail": "Token inválido o expirado."}
```

### `POST /api/usuarios/auth/password-reset/confirm/<uidb64>/<token>/`

Público. Restablece contraseña usando token válido.

Body:

| Campo | Tipo | Requerido | Validaciones |
|---|---:|---:|---|
| `new_password` | string | Sí | Mínimo 8 y validadores de Django. |
| `new_password_confirm` | string | Sí | Debe coincidir. |

Respuesta `200`:

```json
{
  "detail": "Contraseña restablecida correctamente."
}
```

### `GET /api/usuarios/clientes/`

Privado. Requiere rol `Administrador`. Lista todos los usuarios que tienen el rol `Cliente`. Los resultados están ordenados por apellido y nombre.

Respuesta `200`: Array de objetos de usuario.

```json
[
  {
    "id": 1,
    "correo": "cliente@example.com",
    "nombre": "Ana",
    "apellido": "Perez",
    "telefono": "3001234567",
    "direccion": "Calle 1 # 2-3",
    "rol": "Cliente",
    "is_perfil_completo": true,
    "is_active": true,
    "created_at": "2026-05-24T00:00:00Z",
    "updated_at": "2026-05-24T00:00:00Z"
  }
]
```

### `GET /api/usuarios/clientes/<id>/`

Privado. Requiere rol `Administrador`. Obtiene el detalle de un usuario específico, asegurando que tenga el rol `Cliente`.

Respuesta `200`: Objeto de usuario.

Respuesta `404`:

```json
{"detail": "No encontrado."}
```
*(Ocurre si el ID no existe o pertenece a un usuario que no es Cliente).*

## Inventario

Base: `/api/inventario/`

### Uso Público vs Privado

Para tienda pública:

- `GET /api/inventario/public/productos/`
- `GET /api/inventario/public/ingredientes/`
- `GET /api/inventario/public/producto-ingredientes/`

Para panel administrativo:

- `/api/inventario/ingredientes/`
- `/api/inventario/productos/`
- `/api/inventario/producto-ingredientes/`
- `/api/inventario/movimientos-ingrediente/`
- `/api/inventario/movimientos-producto/`
- `/api/inventario/producciones/`
- `/api/inventario/producciones/proximas-a-vencer/`

Los privados de inventario requieren JWT y permiso `IsAdministrador`.

### Modelos de Inventario

#### Ingrediente

| Campo | Tipo | Requerido al crear | Público | Validaciones / Notas |
|---|---:|---:|---:|---|
| `id` | integer | No | Sí | Autogenerado. |
| `nombre` | string, max 100 | Sí | Sí | No puede ser vacío. |
| `proveedor` | string, max 100 | Sí | No en endpoint público | No puede ser vacío. |
| `stock_actual` | decimal string, 10 dígitos, 2 decimales | Sí | Sí | Debe ser `> 0` por serializer. |
| `stock_minimo` | decimal string, 10 dígitos, 2 decimales | Sí | Sí | Debe ser `> 0` por serializer. |
| `unidad_medida` | string | Sí | Sí | Opciones: `kg`, `g`, `l`, `ml`. |

#### Producto

| Campo | Tipo | Requerido al crear | Público | Validaciones / Notas |
|---|---:|---:|---:|---|
| `id` | integer | No | Sí | Autogenerado. |
| `nombre` | string, max 100 | Sí | Sí | No puede ser vacío. |
| `precio` | decimal string, 10 dígitos, 2 decimales | Sí | Sí | Debe ser `> 0`. |
| `stock_actual` | integer | Sí | Sí | Mínimo `0`. |
| `stock_minimo` | integer | Sí | Sí | Mínimo `0`. |
| `inhabilitado` | boolean | No | Sí | Default `false`; el endpoint público solo devuelve `false`. |
| `descripcion` | text/null | No | Sí | Puede ser `null` o texto vacío. |
| `ingredientes` | array de IDs | No | Sí | ManyToMany through `ProductoIngrediente`; se recomienda administrar cantidades desde `producto-ingredientes`. |

#### ProductoIngrediente

| Campo | Tipo | Requerido al crear | Público | Validaciones / Notas |
|---|---:|---:|---:|---|
| `id` | integer | No | Sí | Autogenerado. |
| `id_producto` | integer | Sí | Sí | ID de producto existente. |
| `id_ingrediente` | integer | Sí | Sí | ID de ingrediente existente. |
| `cantidad_ingrediente` | decimal string, 10 dígitos, 2 decimales | Sí | Sí | Debe ser `> 0`. |
| `porcentaje_ingrediente` | decimal string, 5 dígitos, 2 decimales | Sí | Sí | Debe ser `> 0` y `<= 100`. |

#### Produccion

Cada registro de `Produccion` representa un lote producido.

| Campo | Tipo | Requerido al crear | Validaciones / Notas |
|---|---:|---:|---|
| `id` | integer | No | Autogenerado. |
| `id_producto` | integer | Sí | Producto existente. |
| `cantidad_producida` | integer | Sí | Mínimo `1`. |
| `fecha_creacion` | datetime | No | Solo lectura; se genera automáticamente. |
| `fecha_vencimiento` | datetime/null | Sí por API de creación | Fecha/hora de vencimiento; acepta ISO 8601 o `YYYY-MM-DD`. |

Al crear una producción con `POST /api/inventario/producciones/`, el backend:

1. Bloquea el producto con `select_for_update`.
2. Valida stock suficiente de cada ingrediente.
3. Descuenta ingredientes según `cantidad_ingrediente * cantidad_producida`.
4. Crea movimientos de ingrediente tipo `SALIDA`.
5. Aumenta `Producto.stock_actual`.
6. Crea movimiento de producto tipo `ENTRADA`.
7. Crea el registro de producción.
8. Dispara señales de stock y vencimiento asociadas al guardado de modelos.

#### MovimientoIngrediente

| Campo | Tipo | Requerido al crear | Validaciones / Notas |
|---|---:|---:|---|
| `id` | integer | No | Autogenerado. |
| `id_ingrediente` | integer | Sí | Ingrediente existente. |
| `tipo_movimiento` | string | Sí | Opciones: `ENTRADA`, `SALIDA`, `AJUSTE`. |
| `stock_anterior` | decimal string | No | Solo lectura; se calcula al crear. |
| `stock_posterior` | decimal string | No | Solo lectura; se calcula al crear. |
| `cantidad` | decimal string | Sí | Debe ser `> 0`. |
| `fecha` | datetime | No | Solo lectura; se genera automáticamente. |
| `comentarios` | string/null | No | Texto opcional. |

Comportamiento por `tipo_movimiento`:

- `ENTRADA`: suma `cantidad` al stock actual.
- `SALIDA`: resta `cantidad`; si no hay stock suficiente responde `400`.
- `AJUSTE`: establece `stock_actual = cantidad`.

Los movimientos son historiales: se pueden listar, consultar y crear, pero no editar ni eliminar por API.

#### MovimientoProducto

| Campo | Tipo | Requerido al crear | Validaciones / Notas |
|---|---:|---:|---|
| `id` | integer | No | Autogenerado. |
| `id_producto` | integer | Sí | Producto existente. |
| `tipo_movimiento` | string | Sí | Opciones: `ENTRADA`, `SALIDA`, `AJUSTE`. |
| `stock_anterior` | integer | No | Solo lectura; se calcula al crear. |
| `stock_posterior` | integer | No | Solo lectura; se calcula al crear. |
| `cantidad` | integer | Sí | Mínimo `1`. |
| `fecha` | datetime | No | Solo lectura; se genera automáticamente. |
| `comentarios` | string/null | No | Texto opcional. |

Comportamiento por `tipo_movimiento`:

- `ENTRADA`: suma `cantidad` al stock actual.
- `SALIDA`: resta `cantidad`; si no hay stock suficiente responde `400`.
- `AJUSTE`: establece `stock_actual = cantidad`.

Los movimientos son historiales: se pueden listar, consultar y crear, pero no editar ni eliminar por API.

### Endpoints Públicos de Tienda

#### `GET /api/inventario/public/productos/`

Público. Lista productos habilitados. Excluye productos con `inhabilitado=true`.

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
    "descripcion": "Producto demo para catálogo",
    "ingredientes": [1, 2]
  }
]
```

#### `GET /api/inventario/public/ingredientes/`

Público. Lista ingredientes sin exponer proveedor.

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

Campo oculto solo aquí:

- `proveedor`

#### `GET /api/inventario/public/producto-ingredientes/`

Público. Lista relaciones producto-ingrediente.

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

### Endpoints Privados de Inventario - Router

Los siguientes endpoints son generados por `DefaultRouter`. Todos requieren JWT y permiso `IsAdministrador`.

Para recursos CRUD (`ingredientes`, `productos`, `producto-ingredientes`):

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/inventario/<recurso>/` | Listar. |
| `POST` | `/api/inventario/<recurso>/` | Crear. |
| `GET` | `/api/inventario/<recurso>/<id>/` | Obtener detalle. |
| `PUT` | `/api/inventario/<recurso>/<id>/` | Reemplazar completo. |
| `PATCH` | `/api/inventario/<recurso>/<id>/` | Actualizar parcial. |
| `DELETE` | `/api/inventario/<recurso>/<id>/` | Eliminar. |

Para historiales (`movimientos-ingrediente`, `movimientos-producto`):

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/inventario/<recurso>/` | Listar histórico. |
| `POST` | `/api/inventario/<recurso>/` | Crear movimiento y actualizar stock. |
| `GET` | `/api/inventario/<recurso>/<id>/` | Obtener detalle. |
| `PUT` | `/api/inventario/<recurso>/<id>/` | No permitido; responde `405`. |
| `PATCH` | `/api/inventario/<recurso>/<id>/` | No permitido; responde `405`. |
| `DELETE` | `/api/inventario/<recurso>/<id>/` | No permitido; responde `405`. |

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

- `nombre` y `proveedor` no pueden ser vacíos.
- `stock_actual` y `stock_minimo` deben ser decimales `> 0`.
- `unidad_medida`: `kg`, `g`, `l`, `ml`.

#### `PATCH /api/inventario/ingredientes/<id>/`

Actualiza parcialmente cualquier campo enviado.

#### `DELETE /api/inventario/ingredientes/<id>/`

Elimina el ingrediente si no tiene registros protegidos relacionados.

Si existen movimientos de ingrediente u otras referencias protegidas, responde `400`:

```json
{"detail": "No se puede eliminar porque existen registros relacionados."}
```

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
  "inhabilitado": false,
  "descripcion": "Producto demo para catálogo"
}
```

Validaciones:

- `nombre` no puede ser vacío.
- `precio` debe ser decimal `> 0`.
- `stock_actual` y `stock_minimo` deben ser enteros `>= 0`.
- `inhabilitado` es opcional; default `false`.
- `descripcion` es opcional; puede ser texto, `null` o cadena vacía.
- `ingredientes` puede enviarse como array de IDs, pero para cantidades y porcentajes se recomienda `producto-ingredientes`.

#### `PATCH /api/inventario/productos/<id>/`

Actualiza parcialmente un producto.

Ejemplo:

```json
{
  "inhabilitado": true
}
```

#### `DELETE /api/inventario/productos/<id>/`

Elimina el producto si no tiene registros protegidos relacionados.

Si existen producciones, movimientos de producto u otras referencias protegidas, responde `400`:

```json
{"detail": "No se puede eliminar porque existen registros relacionados."}
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

Lista el histórico de movimientos de ingredientes.

#### `GET /api/inventario/movimientos-ingrediente/<id>/`

Obtiene el detalle de un movimiento de ingrediente.

#### `POST /api/inventario/movimientos-ingrediente/`

Crea un movimiento manual de ingrediente y actualiza `Ingrediente.stock_actual`.

Body:

```json
{
  "id_ingrediente": 1,
  "tipo_movimiento": "SALIDA",
  "cantidad": "2.50",
  "comentarios": "Ajuste manual"
}
```

Respuesta `201`:

```json
{
  "id": 1,
  "stock_anterior": "100.00",
  "stock_posterior": "97.50",
  "cantidad": "2.50",
  "fecha": "2026-05-24T13:30:00Z",
  "tipo_movimiento": "SALIDA",
  "comentarios": "Ajuste manual",
  "id_ingrediente": 1
}
```

Error por stock insuficiente:

```json
["Stock insuficiente para realizar la salida."]
```

### Movimientos de Producto Privado

Base: `/api/inventario/movimientos-producto/`

#### `GET /api/inventario/movimientos-producto/`

Lista el histórico de movimientos de productos.

#### `GET /api/inventario/movimientos-producto/<id>/`

Obtiene el detalle de un movimiento de producto.

#### `POST /api/inventario/movimientos-producto/`

Crea un movimiento manual de producto y actualiza `Producto.stock_actual`.

Body:

```json
{
  "id_producto": 1,
  "tipo_movimiento": "ENTRADA",
  "cantidad": 5,
  "comentarios": "Ajuste manual"
}
```

Respuesta `201`:

```json
{
  "id": 1,
  "stock_anterior": 10,
  "stock_posterior": 15,
  "cantidad": 5,
  "fecha": "2026-05-24T13:30:00Z",
  "tipo_movimiento": "ENTRADA",
  "comentarios": "Ajuste manual",
  "id_producto": 1
}
```

Error por stock insuficiente:

```json
["Stock insuficiente para realizar la salida."]
```

### Producciones

Base: `/api/inventario/producciones/`

#### `GET /api/inventario/producciones/`

Privado. Requiere JWT y permiso `IsAdministrador`. Lista producciones ordenadas por `fecha_creacion` descendente.

Respuesta `200`:

```json
[
  {
    "id": 1,
    "cantidad_producida": 10,
    "fecha_creacion": "2026-05-24T13:30:00Z",
    "fecha_vencimiento": "2026-06-24T00:00:00Z",
    "id_producto": 1
  }
]
```

#### `POST /api/inventario/producciones/`

Privado. Requiere JWT y permiso `IsAdministrador`. Crea una producción y actualiza inventario en una transacción.

Body:

```json
{
  "id_producto": 1,
  "cantidad_producida": 10,
  "fecha_vencimiento": "2026-06-24"
}
```

Validaciones:

- `id_producto` es requerido y debe ser entero.
- `cantidad_producida` es requerida, debe ser entero y debe ser mayor que `0`.
- `fecha_vencimiento` es requerida y debe ser fecha/hora válida.
- El producto debe existir.
- Debe haber stock suficiente de ingredientes según las relaciones `ProductoIngrediente`.

Respuesta `201`:

```json
{
  "id": 1,
  "cantidad_producida": 10,
  "fecha_creacion": "2026-05-24T13:30:00Z",
  "fecha_vencimiento": "2026-06-24T00:00:00Z",
  "id_producto": 1
}
```

Errores:

```json
{"detail": "id_producto, cantidad_producida y fecha_vencimiento son requeridos."}
```

```json
{"detail": "cantidad_producida debe ser un entero."}
```

```json
{"detail": "fecha_vencimiento debe ser una fecha/hora valida."}
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
- Ejecuta señales de notificación asociadas a stock y vencimiento.

#### `GET /api/inventario/producciones/proximas-a-vencer/`

Privado. Requiere JWT y permiso `IsAdministrador`. Solo permite consulta por `GET`.

Lista los lotes de producción cuya `fecha_vencimiento` cumple:

- Fecha de vencimiento mayor o igual a la fecha actual.
- Fecha de vencimiento menor o igual a un mes calendario desde la fecha actual.
- `fecha_vencimiento` no nula.

Detalles de cálculo:

- El endpoint compara por fecha calendario usando `timezone.localdate()`.
- No compara por hora exacta, por lo que un lote que vence hoy se incluye.
- El límite superior es un mes calendario, no un rango fijo de 30 días.
- La respuesta se ordena por `fecha_vencimiento` ascendente y luego por `id`.
- No crea notificaciones ni modifica inventario; solo consulta la tabla `produccion`.

Respuesta `200`:

```json
[
  {
    "id": 8,
    "cantidad_producida": 20,
    "fecha_creacion": "2026-05-24T13:30:00Z",
    "fecha_vencimiento": "2026-06-15T00:00:00Z",
    "id_producto": 1
  },
  {
    "id": 9,
    "cantidad_producida": 12,
    "fecha_creacion": "2026-05-25T10:00:00Z",
    "fecha_vencimiento": "2026-06-24T00:00:00Z",
    "id_producto": 2
  }
]
```

Si no hay lotes próximos a vencer:

```json
[]
```

Métodos no permitidos:

- `POST /api/inventario/producciones/proximas-a-vencer/` responde `405`.
- `PUT /api/inventario/producciones/proximas-a-vencer/` responde `405`.
- `PATCH /api/inventario/producciones/proximas-a-vencer/` responde `405`.
- `DELETE /api/inventario/producciones/proximas-a-vencer/` responde `405`.

## Notificaciones

Base: `/api/notificaciones/`

La app `notificaciones` sí está montada en `project/urls.py` y sí expone API. Esta sección reemplaza la información contradictoria anterior.

### Modelo Notificacion

| Campo | Tipo | Expuesto en API | Descripción |
|---|---:|---:|---|
| `id` | integer | Sí | ID de la notificación. |
| `usuario` | FK Usuario/null | No directo | Usuario asociado, si aplica. |
| `producto` | FK Producto/null | Como `source_type/source_id` | Producto asociado, si aplica. |
| `ingrediente` | FK Ingrediente/null | Como `source_type/source_id` | Ingrediente asociado, si aplica. |
| `credito` | FK Credito/null | Como `source_type/source_id` | Crédito asociado, si aplica. |
| `cuota_credito` | FK CuotaCredito/null | Como `source_type/source_id` | Cuota asociada, si aplica. |
| `tipo` | string | Sí | Tipo técnico de notificación. |
| `tipo_display` | string | Sí | Nombre legible del tipo. |
| `mensaje` | text | Sí | Mensaje mostrado al usuario. |
| `leida` | boolean | Sí | `false` para activa, `true` para resuelta. |
| `fecha_generada` | datetime | Sí | Fecha de creación o actualización de alerta. |
| `fecha_leida` | datetime/null | Sí | Fecha en que se resolvió. |
| `source_type` | string/null | Sí | `producto`, `ingrediente`, `credito`, `cuota_credito` o `null`. |
| `source_id` | integer/null | Sí | ID del origen asociado. |

Restricción de integridad del modelo:

- Una notificación puede tener como máximo una referencia de origen entre producto, ingrediente, crédito o cuota.

Tipos soportados en `tipo`:

- `stock_producto`
- `stock_ingrediente`
- `vencimiento_producto`
- `deuda_vencida`
- `deuda_proxima`

### `GET /api/notificaciones/`

Privado. Requiere usuario autenticado. El queryset solo devuelve notificaciones para usuarios con rol `Administrador`.

Comportamiento por tipo de usuario:

- Usuario anónimo: `401`.
- Usuario autenticado sin rol `Administrador`: `200` con `[]`.
- Usuario autenticado con rol `Administrador`: `200` con notificaciones activas (`leida=false`).

Respuesta `200`:

```json
[
  {
    "id": 15,
    "tipo": "stock_producto",
    "tipo_display": "Stock Producto",
    "mensaje": "El producto 'Carne Premium' tiene stock bajo (2). Mínimo: 10.",
    "leida": false,
    "fecha_generada": "2026-05-31T12:20:00Z",
    "fecha_leida": null,
    "source_type": "producto",
    "source_id": 42
  }
]
```

Uso recomendado de `source_type` y `source_id`:

- Si `source_type` es `producto`, redirigir al detalle del producto con `source_id`.
- Si `source_type` es `ingrediente`, redirigir al detalle del ingrediente con `source_id`.
- Si `source_type` es `credito` o `cuota_credito`, redirigir al módulo de créditos cuando exista API o vista frontend.

### `PATCH /api/notificaciones/<id>/resolve/`

Privado. Marca una alerta como resuelta (`leida=true`) y asigna `fecha_leida`.

Body: no requiere body.

Respuesta `200`:

```json
{
  "status": "Notificación resuelta"
}
```

Comportamiento:

- Usuario anónimo: `401`.
- Usuario autenticado sin rol `Administrador`: normalmente `404`, porque su queryset visible está vacío.
- Usuario administrador con ID existente visible: `200`.

### Generación de Notificaciones

Las notificaciones se crean o resuelven desde servicios y señales, no desde endpoints públicos de creación.

Eventos actuales:

- Al guardar `Producto`, se evalúa stock bajo contra `stock_minimo`.
- Al guardar `Ingrediente`, se evalúa stock bajo contra `stock_minimo`.
- Al guardar `Produccion`, se evalúa vencimiento próximo con ventana de 7 días en la señal actual.

Notas importantes:

- El endpoint `/api/inventario/producciones/proximas-a-vencer/` usa una ventana de un mes calendario y solo consulta datos.
- La señal de notificación por vencimiento usa una ventana de 7 días y puede crear o resolver notificaciones.
- Son comportamientos distintos y ambos están documentados aquí para evitar confusión.

## Panel Admin de Django

Ruta web:

```txt
/admin/
```

No es API JSON. Es el panel administrativo de Django.

Modelos registrados actualmente:

- `Ingrediente`
- `Producto`
- `ProductoIngrediente`
- `Produccion`
- `MovimientoIngrediente`
- `MovimientoProducto`
- `Rol`
- `Usuario`

Notas:

- Crear una `Produccion` desde el admin ejecuta `services.crear_produccion`.
- Por tanto descuenta ingredientes, aumenta stock del producto y crea movimientos.
- Si no hay stock suficiente, el formulario muestra error de validación.
- `Ventas`, `Creditos` y `Notificacion` tienen modelos, pero no están registrados en admin actualmente.

## Apps con Modelos pero sin API Expuesta

Estas apps existen en `INSTALLED_APPS`, pero actualmente no están montadas en `project/urls.py` con endpoints propios.

### Ventas

Modelos:

- `CarritoDeCompras`
- `Pedido`
- `PedidoProducto`

Estado API:

- No hay `/api/ventas/` montado actualmente.
- `apps/ventas/views.py` no implementa endpoints.

### Creditos

Modelos:

- `Credito`
- `CuotaCredito`

Estado API:

- No hay `/api/creditos/` montado actualmente.
- `apps/creditos/views.py` no implementa endpoints.

## Recomendaciones para Frontend

### Tienda Pública

Usar:

- `GET /api/inventario/public/productos/`
- `GET /api/inventario/public/ingredientes/`
- `GET /api/inventario/public/producto-ingredientes/`
- `POST /api/usuarios/auth/register/`
- `POST /api/usuarios/auth/login/`
- `POST /api/usuarios/auth/google/`
- `POST /api/usuarios/auth/password-reset/`
- `GET /api/usuarios/auth/password-reset/confirm/<uidb64>/<token>/`
- `POST /api/usuarios/auth/password-reset/confirm/<uidb64>/<token>/`

No enviar JWT en endpoints públicos; no lo necesitan.

### Usuario Autenticado

Usar:

- `GET /api/usuarios/me/`
- `PATCH /api/usuarios/me/`
- `POST /api/usuarios/auth/change-password/`
- `POST /api/usuarios/auth/logout/`
- `POST /api/usuarios/auth/refresh/`

Estos endpoints requieren token, pero no rol `Administrador`.

### Panel Administrativo Frontend

Usar JWT de un usuario con rol `Administrador`.

Inventario:

- CRUD de ingredientes.
- CRUD de productos.
- CRUD de producto-ingredientes.
- `POST /api/inventario/producciones/` para producir y mover stock correctamente.
- `GET /api/inventario/producciones/proximas-a-vencer/` para revisar lotes que vencen entre hoy y un mes calendario.
- `POST /api/inventario/movimientos-ingrediente/` para ajustes manuales de stock de ingredientes.
- `POST /api/inventario/movimientos-producto/` para ajustes manuales de stock de productos.
- `GET /api/inventario/movimientos-ingrediente/` y `GET /api/inventario/movimientos-producto/` para históricos.

Notificaciones:

- `GET /api/notificaciones/` para alertas activas.
- `PATCH /api/notificaciones/<id>/resolve/` para marcar una alerta como resuelta.

Evitar:

- Editar o eliminar movimientos; son historiales y la API responde `405`.
- Usar endpoints públicos para administración, porque ocultan o simplifican información.
- Crear producciones modificando stock manualmente; usar `POST /api/inventario/producciones/` para mantener movimientos y stock coherentes.

## Pendientes Técnicos Detectados

Estos puntos no bloquean el consumo actual, pero son importantes para planificación:

- No hay API implementada para ventas, carrito ni pedidos.
- No hay API implementada para créditos.
- Los endpoints de listado no tienen paginación, filtros ni búsqueda configurados.
- Los permisos privados de inventario están centralizados en rol `Administrador`; no hay permisos granulares por acción.
- Notificaciones usa `IsAuthenticated` y filtra administradores en queryset; si se quiere consistencia con inventario, podría migrarse a permiso explícito de administrador.
