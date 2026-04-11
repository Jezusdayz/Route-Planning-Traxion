document.addEventListener('DOMContentLoaded', function () {
    // --- VARIABLES GLOBALES ---
    let fuelVal = 100;
    let distanceTraveled = 0;
    let totalTripDistance = 0;
    let viajeActivo = false;
    let ws = null; // Conexión WebSocket

    // --- CONFIGURACIÓN MARKED ---
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            breaks: true,
            gfm: true
        });
    }

    // --- EVENT LISTENERS ---
    const userInput = document.getElementById('user-input');
    if (userInput) {
        userInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
    }

    // --- 1. LÓGICA DEL MAPA (Mantenida) ---
    const map = new maplibregl.Map({
        container: 'mapa',
        style: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
        center: [-99.1332, 19.4326],
        zoom: 12,
        trackResize: true
    });
    map.addControl(new maplibregl.NavigationControl());
    map.on('load', () => { map.resize(); });

    let markerOrigen = null;
    let markerDestino = null;

    // --- 2. LÓGICA DEL FORMULARIO Y TRACY (API REAL) ---
    window.startAgent = async function () {
        const origin = document.getElementById('route-origin').value;
        const dest = document.getElementById('route-dest').value;
        const passengersTotal = document.getElementById('passengers').value;
        const serviceLevel = document.getElementById('service-level').value;
        const date = document.getElementById('service-date').value;
        const time = document.getElementById('service-time').value;

        if (!origin || !dest || !passengersTotal || !serviceLevel || !date || !time) {
            alert("Por favor completa todos los campos para configurar el servicio.");
            return;
        }

        const btn = document.getElementById('start-chat-btn');
        btn.innerText = "Conectando con Tracy...";
        btn.disabled = true;

        try {
            // PASO 1: HTTP POST para iniciar la cotización en el Backend
            const response = await fetch('http://localhost:8000/cotizar/iniciar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    origen: origin,
                    destino: dest,
                    pasajeros: parseInt(passengersTotal),
                    nivel_servicio: serviceLevel,
                    fecha_servicio: date,
                    hora_salida: time
                })
            });

            if (!response.ok) {
                const errData = await response.json();
                let msg = "Verifica los datos";
                if (typeof errData.detail === 'string') msg = errData.detail;
                else if (errData.detail && errData.detail.detail) msg = errData.detail.detail;
                else if (errData.detail && errData.detail.error) msg = errData.detail.error;
                
                alert(`Tracy: ${msg}`);
                btn.innerText = "Iniciar Tracy";
                btn.disabled = false;
                return;
            }

            const data = await response.json();
            const sessionToken = data.token;

            // --- CAMBIO DE INTERFAZ ---
            document.getElementById('setup-form').style.display = 'none';
            const chatContainer = document.getElementById('chat-container');
            chatContainer.style.display = 'flex';
            
            const chatWindow = document.getElementById('chat-window');
            chatWindow.innerHTML = `<div class="bot-msg" style="color: #666;"><div class="msg-content"><em>Conectando al canal seguro...</em></div></div>`;

            // PASO 2: CONECTAR WEBSOCKET
            conectarWebSocket(sessionToken);

            // El backend devuelve los datos del estado directamente en la raíz de la respuesta
            procesarActualizacionEstado(data);

        } catch (error) {
            alert("Error al conectar con el servidor backend (FastAPI en puerto 8000).");
            console.error(error);
            btn.innerText = "Iniciar Tracy";
            btn.disabled = false;
        }
    };

    function conectarWebSocket(token) {
        const wsUrl = `ws://localhost:8000/chat/${token}`;
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            const chatWindow = document.getElementById('chat-window');
            chatWindow.innerHTML = `<div class="bot-msg" style="color: #666;"><div class="msg-content"><em>Conexión establecida. Esperando a Tracy...</em></div></div>`;
            chatWindow.scrollTop = chatWindow.scrollHeight;

            const statusText = document.getElementById('chat-status-text');
            if (statusText) statusText.innerText = "En línea";
        };

        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            const chatWindow = document.getElementById('chat-window');
            
            // El backend usa 'type' para estatus y 'tipo' para mensajes de negocio
            const msgType = msg.type || msg.tipo;

            if (msgType === "status") {
                const isThinking = msg.data ? msg.data.is_thinking : msg.is_thinking;
                const btnSend = document.getElementById('send-btn');
                const btnText = document.getElementById('btn-text');
                const btnLoader = document.getElementById('btn-loader');
                const inputChat = document.getElementById('user-input');
                const statusText = document.getElementById('chat-status-text');
                const statusDot = document.querySelector('.status-dot');

                if (isThinking) {
                    btnSend.disabled = true;
                    inputChat.disabled = true;
                    inputChat.placeholder = "Tracy está pensando...";
                    if (btnText) btnText.innerText = "Pensando";
                    if (btnLoader) btnLoader.style.display = 'inline-block';
                    if (statusText) statusText.innerText = "Tracy está pensando...";
                    if (statusDot) {
                        statusDot.classList.remove('online');
                        statusDot.classList.add('thinking');
                    }
                } else {
                    btnSend.disabled = false;
                    inputChat.disabled = false;
                    inputChat.placeholder = "Escribe un mensaje...";
                    if (btnText) btnText.innerText = "Enviar";
                    if (btnLoader) btnLoader.style.display = 'none';
                    if (statusText) statusText.innerText = "Esperando input";
                    if (statusDot) {
                        statusDot.classList.remove('thinking');
                        statusDot.classList.add('online');
                    }
                }
            } 
            else if (msgType === "update" || msgType === "bienvenida" || msgType === "respuesta") {
                procesarActualizacionEstado(msg);
            }
            else if (msgType === "error") {
                // El campo puede ser 'mensaje' o 'detail'
                const errorTexto = msg.mensaje || msg.detail || "Error desconocido";
                const htmlContent = typeof marked !== 'undefined' ? marked.parse(errorTexto) : errorTexto;
                chatWindow.innerHTML += `<div class="bot-msg" style="color:red"><strong>Tracy (Error):</strong> <div class="msg-content">${htmlContent}</div></div>`;
                chatWindow.scrollTop = chatWindow.scrollHeight;
            }
        };

        ws.onclose = () => {
            const chatWindow = document.getElementById('chat-window');
            chatWindow.innerHTML += `<div class="bot-msg" style="color:orange"><strong>Sistema:</strong> Chat desconectado.</div>`;
        };
    }

    function procesarActualizacionEstado(estado) {
        const chatWindow = document.getElementById('chat-window');

        // Tracy envía mensaje_usuario directamente en la raíz para 'bienvenida' y 'respuesta'
        const textoTracy = (estado.explicacion && estado.explicacion.mensaje_usuario) 
                           ? estado.explicacion.mensaje_usuario 
                           : estado.mensaje_usuario;

        if (textoTracy) {
            const htmlContent = typeof marked !== 'undefined' ? marked.parse(textoTracy) : textoTracy;
            chatWindow.innerHTML += `<div class="bot-msg"><strong>Tracy:</strong> <div class="msg-content">${htmlContent}</div></div>`;
            chatWindow.scrollTop = chatWindow.scrollHeight;
        }

        // 2. Actualizar el Panel de Monitoreo
        // El objeto de resultado puede venir en estado.resultado o estado.data.resultado
        const res = estado.resultado || (estado.data && estado.data.resultado);
        if (res) {
            totalTripDistance = res.distancia_total_km || 0;
            document.getElementById('calc-dist').innerText = `${totalTripDistance} km`;
            document.getElementById('calc-fuel-cost').innerText = `$${res.costo_total ? res.costo_total.toFixed(2) : 0}`;
            
            const inputU = estado.input_usuario || (estado.data && estado.data.input_usuario);
            if(inputU) {
                document.getElementById('calc-passengers').innerText = `${inputU.pasajeros}`;
            }

            const btnViaje = document.getElementById('btn-iniciar-viaje');
            if (btnViaje) {
                btnViaje.style.display = 'block';
                btnViaje.innerText = "Iniciar Viaje";
                btnViaje.disabled = false;
                btnViaje.style.background = "rgb(208, 223, 0)";
            }
            viajeActivo = false;
            distanceTraveled = 0;
            fuelVal = 100;
        }

        // 3. Trazar ruta en el mapa
        const norm = estado.normalizacion || (estado.data && estado.data.normalizacion);
        if (norm && norm.origen && norm.destino) {
            const coordsOrigen = [norm.origen.lon, norm.origen.lat];
            const coordsDestino = [norm.destino.lon, norm.destino.lat];
            
            if(!markerOrigen) markerOrigen = new maplibregl.Marker({ color: "#28a745" }).setLngLat(coordsOrigen).addTo(map);
            else markerOrigen.setLngLat(coordsOrigen);
            
            if(!markerDestino) markerDestino = new maplibregl.Marker({ color: "#dc3545" }).setLngLat(coordsDestino).addTo(map);
            else markerDestino.setLngLat(coordsDestino);
            
            trazarRuta(coordsOrigen, coordsDestino);
            
            const bounds = new maplibregl.LngLatBounds(coordsOrigen, coordsOrigen);
            bounds.extend(coordsDestino);
            map.fitBounds(bounds, { padding: 50 });
        }

        // 4. Justificaciones y Supuestos
        const justificacion = estado.justificacion || (estado.explicacion && estado.explicacion.justificacion);
        const supuestos = estado.supuestos_clave || (estado.explicacion && estado.explicacion.supuestos_clave);

        if (justificacion) {
            const list = document.getElementById('justificacion-list');
            if (list) {
                list.innerHTML = '';
                const items = Array.isArray(justificacion) ? justificacion : [justificacion];
                items.forEach(item => {
                    const li = document.createElement('li');
                    li.textContent = item;
                    list.appendChild(li);
                });
            }
        }

        if (supuestos) {
            const list = document.getElementById('supuestos-list');
            if (list) {
                list.innerHTML = '';
                const items = Array.isArray(supuestos) ? supuestos : [supuestos];
                items.forEach(item => {
                    const li = document.createElement('li');
                    li.textContent = item;
                    list.appendChild(li);
                });
            }
        }
    }

    window.sendMessage = function () {
        const input = document.getElementById('user-input');
        const chatWindow = document.getElementById('chat-window');
        const message = input.value.trim();

        if (!message || !ws || ws.readyState !== WebSocket.OPEN) return;

        chatWindow.innerHTML += `<div class="user-msg"><strong>Tú:</strong> ${message}</div>`;
        input.value = '';
        chatWindow.scrollTop = chatWindow.scrollHeight;

        ws.send(message);
    };

    window.activarTelemetria = function () {
        viajeActivo = true;
        const btnViaje = document.getElementById('btn-iniciar-viaje');
        btnViaje.innerText = "En Trayecto...";
        btnViaje.style.background = "#eee";
        btnViaje.disabled = true;

        const chatWindow = document.getElementById('chat-window');
        const msg = "El despacho ha sido autorizado. He iniciado el monitoreo de combustible y progreso para la unidad. ¡Buen viaje!";
        const htmlContent = typeof marked !== 'undefined' ? marked.parse(msg) : msg;
        chatWindow.innerHTML += `
            <div class="bot-msg">
                <strong>Tracy:</strong>
                <div class="msg-content">${htmlContent}</div>
            </div>`;
        chatWindow.scrollTop = chatWindow.scrollHeight;
    };

    function trazarRuta(inicio, fin) {
        const geojson = {
            'type': 'Feature',
            'geometry': { 'type': 'LineString', 'coordinates': [inicio, fin] }
        };
        if (map.getSource('route')) {
            map.getSource('route').setData(geojson);
        } else {
            map.addLayer({
                'id': 'route',
                'type': 'line',
                'source': { 'type': 'geojson', 'data': geojson },
                'layout': { 'line-join': 'round', 'line-cap': 'round' },
                'paint': { 'line-color': 'rgb(208, 223, 0)', 'line-width': 5, 'line-opacity': 0.8 }
            });
        }
    }

    function updateMini() {
        if (!viajeActivo || totalTripDistance === 0) return;

        const fBar = document.getElementById('fuel-bar');
        const fText = document.getElementById('fuel-text');
        const dBar = document.getElementById('dist-bar');
        const dVal = document.getElementById('dist-val');

        if (fBar && fText) {
            fuelVal = Math.max(0, fuelVal - 0.08);
            fBar.style.width = fuelVal + "%";
            fText.innerText = Math.round(fuelVal) + "%";
            if (fuelVal < 20) fBar.style.background = "#dc3545";
        }

        if (dBar && dVal && distanceTraveled < totalTripDistance) {
            distanceTraveled += (totalTripDistance / 200);
            dVal.innerText = distanceTraveled.toFixed(1);
            dBar.style.width = ((distanceTraveled / totalTripDistance) * 100) + "%";
        }
    }
    setInterval(updateMini, 1500);
});