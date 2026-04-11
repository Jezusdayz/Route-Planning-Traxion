# Guía de Integración Frontend: Tracy Intelligence

Esta guía detalla cómo el equipo de Frontend debe interactuar con el backend de Tracy para ofrecer una experiencia fluida de cotización y chat logístico.

## 1. Protocolo de Comunicación Híbrido

Tracy utiliza un flujo de dos pasos para garantizar que solo los servicios validados puedan acceder al chat en tiempo real.

### Paso 1: Configuración Inicial (HTTP)
**Endpoint**: `POST /cotizar/iniciar`  
**Payload**:
```json
{
  "origen": "string",
  "destino": "string",
  "pasajeros": number,
  "nivel_servicio": "economico" | "empresarial" | "ejecutivo",
  "fecha_servicio": "YYYY-MM-DD",
  "hora_salida": "HH:MM"
}
```
**Respuesta Exitosa (200 OK)**:
```json
{
  "token": "uuid-v4-access-token",
  "ws_url": "ws://api.traxion.com/chat/uuid-v4-token",
  "estado_inicial": { ... } // El Gran JSON completo
}
```

### Paso 2: Conexión al Chat (WebSocket)
**Endpoint**: `ws://api.traxion.com/chat/{token}`  
**Misión**: Una vez conectado, el chat se convierte en el canal de actualización dinámica.

---

## 2. Gestión de Estados (UX)

### El Flag `is_thinking` (Crítico)
El backend enviará mensajes de estado por el WebSocket. El frontend **DEBE** reaccionar a ellos:
- **`is_thinking: true`**: Bloquear el input del chat y mostrar un spinner o mensaje de "Tracy está recalculando...".
- **`is_thinking: false`**: Desbloquear el input y permitir que el usuario escriba.

**Ejemplo de Mensaje de Estado**:
```json
{
  "type": "status",
  "data": {
    "is_thinking": true,
    "fase": "costeo"
  }
}
```

---

## 3. Renderizado de la Respuesta de Tracy

Cada vez que se complete un ciclo de cálculo (Fase 8), el WebSocket enviará el objeto de estado actualizado. El frontend debe enfocarse en la rama `explicacion`:

```json
{
  "type": "update",
  "data": {
    "explicacion": {
      "mensaje_usuario": "Texto amigable de Tracy...",
      "justificacion": ["Bullet 1", "Bullet 2"],
      "supuestos_clave": ["Dato 1", "Dato 2"]
    },
    "resultado": {
      "costo_total": 20578.98,
      "vehiculo_seleccionado": "Autobús Ejecutivo"
    }
  }
}
```

---

## 4. Mejores Prácticas
1.  **No persistir historial localmente**: El "Gran JSON" enviado por el servidor siempre contiene el estado más reciente y coherente. Confía siempre en el último mensaje recibido.
2.  **Manejo de Errores**: Si el WebSocket recibe un mensaje con `type: "error"`, muestra el detalle en el chat y permite al usuario corregir su última instrucción.
3.  **Visualización de Ruta**: Si el objeto de estado contiene coordenadas en `normalizacion`, úsalas para renderizar el mapa (Leaflet/Google Maps) de forma asíncrona.

## 5. Pruebas Rápidas
Puedes usar la herramienta `wscat` para simular la conexión del frontend:
`wscat -c ws://localhost:8000/chat/{tu_token}`
