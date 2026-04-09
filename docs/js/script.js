document.addEventListener('DOMContentLoaded', function() {
    // --- 1. LÓGICA DEL MAPA ---
    const map = new maplibregl.Map({
        container: 'mapa', 
        style: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json', 
        center: [-99.1332, 19.4326], 
        zoom: 12,
        trackResize: true
    });
    map.addControl(new maplibregl.NavigationControl());
    map.on('load', () => { map.resize(); });

    // --- 2. LÓGICA DEL FORMULARIO Y TRACY ---
    window.startAgent = function() {
        // Referencias a los campos
        const origin = document.getElementById('route-origin').value;
        const dest = document.getElementById('route-dest').value;
        const passengers = document.getElementById('passengers').value;
        const serviceLevel = document.getElementById('service-level').value;
        const date = document.getElementById('service-date').value;
        const time = document.getElementById('service-time').value;

        // Validación simple
        if(!origin || !dest || !passengers || !serviceLevel || !date || !time) {
            alert("Por favor completa todos los campos para configurar el servicio.");
            return;
        }

        // Cambiar de interfaz: Ocultar form, mostrar chat
        document.getElementById('setup-form').style.display = 'none';
        const chatContainer = document.getElementById('chat-container');
        chatContainer.style.display = 'flex';

        // Saludo inicial personalizado con los datos del form
        const chatWindow = document.getElementById('chat-window');
        chatWindow.innerHTML = `
            <div class="bot-msg">
                <strong>Tracy:</strong> ¡Configuración exitosa! He programado un servicio <strong>${serviceLevel.toUpperCase()}</strong> 
                de <strong>${origin}</strong> a <strong>${dest}</strong> para el día ${date} a las ${time} 
                con ${passengers} pasajeros. ¿En qué más puedo apoyarte?
            </div>
        `;

        // --- Lógica Visual del Mapa ---
        // Coordenadas simuladas para la demo
        const coordsOrigen = [-99.1332, 19.4326]; 
        const coordsDestino = [-99.1676, 19.4270];

        // Añadir marcadores
        new maplibregl.Marker({ color: "#28a745" }).setLngLat(coordsOrigen).addTo(map);
        new maplibregl.Marker({ color: "#dc3545" }).setLngLat(coordsDestino).addTo(map);
        
        // Dibujar la línea azul
        trazarRuta(coordsOrigen, coordsDestino);
        
        // Animación de cámara
        map.flyTo({ center: [-99.1500, 19.4300], zoom: 13, essential: true });
    };

    // Función para dibujar la línea de ruta en el mapa
    function trazarRuta(inicio, fin) {
        const geojson = {
            'type': 'Feature',
            'geometry': {
                'type': 'LineString',
                'coordinates': [inicio, fin]
            }
        };

        if (map.getSource('route')) {
            map.getSource('route').setData(geojson);
        } else {
            map.addLayer({
    'id': 'route',
    'type': 'line',
    'source': {
        'type': 'geojson',
        'data': geojson
    },
    'layout': { 
        'line-join': 'round', 
        'line-cap': 'round' 
    },
    'paint': {
        
        'line-color': 'rgb(208, 223, 0)', 
        'line-width': 5,
        'line-opacity': 0.8
    }
});
        }
    }

    // Lógica del Chat con Gemini
    window.sendMessage = async function() {
        const input = document.getElementById('user-input');
        const chatWindow = document.getElementById('chat-window');
        const message = input.value.trim();
        const API_KEY = "TU_API_KEY_AQUI"; 

        if (!message) return;

        // Mostrar mensaje del usuario
        chatWindow.innerHTML += `<div class="user-msg"><strong>Tú:</strong> ${message}</div>`;
        input.value = '';
        chatWindow.scrollTop = chatWindow.scrollHeight;

        try {
            const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${API_KEY}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ contents: [{ parts: [{ text: message }] }] })
            });
            const data = await response.json();
            
            // Verificación básica de respuesta
            if (data.candidates && data.candidates[0].content.parts[0].text) {
                const botReply = data.candidates[0].content.parts[0].text;
                chatWindow.innerHTML += `<div class="bot-msg"><strong>Tracy:</strong> ${botReply}</div>`;
            } else {
                throw new Error("Respuesta vacía");
            }
        } catch (error) {
            chatWindow.innerHTML += `<div class="bot-msg" style="color:red"><strong>Tracy:</strong> Lo siento, tuve un problema de conexión.</div>`;
        }
        chatWindow.scrollTop = chatWindow.scrollHeight;
    };

    // --- 3. LÓGICA DEL MONITOREO (SIMULACIÓN AUTOMÁTICA) ---
    let fuelVal = 100;
    let distance = 0;
    const totalDist = 14.2;

    function updateMini() {
        const fBar = document.getElementById('fuel-bar');
        const fText = document.getElementById('fuel-text');
        const dBar = document.getElementById('dist-bar');
        const dVal = document.getElementById('dist-val');
        
        if(fBar && fText) {
            fuelVal = Math.max(0, fuelVal - 0.05);
            fBar.style.width = fuelVal + "%";
            fText.innerText = Math.round(fuelVal) + "%";
            // Alerta visual de combustible bajo
            if(fuelVal < 20) fBar.style.background = "#dc3545";
        }

        if(dBar && dVal && distance < totalDist) {
            distance += 0.05;
            dVal.innerText = distance.toFixed(1);
            dBar.style.width = ((distance / totalDist) * 100) + "%";
        }
    }
    // Actualiza los indicadores cada 2 segundos
    setInterval(updateMini, 2000);
});