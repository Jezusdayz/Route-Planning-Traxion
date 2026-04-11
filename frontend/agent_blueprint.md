# Blueprint: Arquitectura Tracy (Traxion Intelligence)

Este sistema utiliza un enfoque de **Estado Único Incremental (Single Source of Truth)** y una orquestación de 8 fases para garantizar cotizaciones de transporte precisas y coherentes.

## 1. El Concepto del "Gran JSON"
A diferencia de sistemas que pierden contexto entre llamadas, Tracy mantiene un único objeto JSON en la sesión de MongoDB. Cada fase (Normalización, Planeación, Costeo) inyecta datos nuevos a este objeto. Al final, Tracy tiene visión total del porqué del costo.

## 2. Ciclo de Vida y "Fase Fantasma"
1. **Inicio Sincrónico**: El usuario llena un formulario (Input Limpio). Se procesa el pipeline 1-8.
2. **Ciclo Asincrónico (Chat)**: Si el usuario dice "Somos 10 más", se activa la **Fase Fantasma**. 
3. **El Gatekeeper**: Tracy extrae la intención, hace un *Merge* con el estado anterior y actualiza el `input_usuario`.
4. **Validación Estricta**: El backend actúa como juez. Si Tracy intenta inventar datos o si un vehículo no tiene autonomía, el sistema detiene el proceso y lanza un error.

## 3. Las 8 Fases del Pipeline
- **Fase 0**: Extracción de Intención (IA Ligera / Gatekeeper).
- **Fase 1**: Input (Estandarización de datos).
- **Fase 2**: Normalización (Geocodificación y limpieza).
- **Fase 3**: Planeación (Cálculo de kilómetros y horas reales - Ida y Vuelta).
- **Fase 4**: Operación (Asignación de unidades específicas).
- **Fase 5**: Validación (¿Es seguro? ¿Cabe la gente? ¿Hay gasolina suficiente?).
- **Fase 6**: Costeo (Cálculo financiero granular por cada tipo de unidad).
- **Fase 7**: Resultado (Resumen ejecutivo del viaje).
- **Fase 8**: Explicación (El toque humano generado por Tracy).

## 4. Filosofía de Eficiencia
- **Backend 100%**: Las fases 1 a 7 ocurren íntegramente en el servidor para evitar alucinaciones y ahorrar tokens.
- **IA Estratégica**: Tracy solo interviene al inicio (entender) y al final (explicar).
- **WebSocket Feedback**: El flag `is_thinking` garantiza que el usuario sepa cuándo Tracy o el Backend están trabajando.