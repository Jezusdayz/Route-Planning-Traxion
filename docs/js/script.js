document.addEventListener('DOMContentLoaded', function () {

    // --- VARIABLES GLOBALES PARA SIMULACIÓN ---

    let fuelVal = 100;

    let distanceTraveled = 0;

    let totalTripDistance = 0;

    let viajeActivo = false; // Controla si la telemetría está corriendo



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

    window.startAgent = function () {

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



        // --- CÁLCULOS DINÁMICOS PARA EL PANEL ---

        totalTripDistance = Math.floor(Math.random() * (45 - 15) + 15);

        const fuelPrice = 24.20;

        const efficiency = 7;

        const estimatedFuelCost = (totalTripDistance / efficiency) * fuelPrice;

        const tollCost = totalTripDistance > 30 ? 148 : 0;

        const currentPassengers = Math.max(0, parseInt(passengersTotal) - 1);



        // Actualizar el DOM del Panel de Monitoreo

        document.getElementById('calc-dist').innerText = `${totalTripDistance} km`;

        document.getElementById('calc-fuel-cost').innerText = `$${estimatedFuelCost.toFixed(2)}`;

        document.getElementById('calc-toll').innerText = `$${tollCost}`;

        document.getElementById('calc-passengers').innerText = `${currentPassengers}/${passengersTotal}`;



        // Mostrar el botón de Iniciar Viaje y resetear estado

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



        // --- CAMBIO DE INTERFAZ ---

        document.getElementById('setup-form').style.display = 'none';

        const chatContainer = document.getElementById('chat-container');

        chatContainer.style.display = 'flex';



        const chatWindow = document.getElementById('chat-window');

        chatWindow.innerHTML = `

<div class="bot-msg">

<strong>Tracy:</strong> ¡Configuración exitosa! He proyectado una ruta de

<strong>${origin}</strong> hacia <strong>${dest}</strong> con una distancia de

<strong>${totalTripDistance} km</strong>.

<br><br>

El costo estimado de combustible es de <strong>$${estimatedFuelCost.toFixed(2)}</strong>

para el nivel de servicio <strong>${serviceLevel.toUpperCase()}</strong>.

¿Deseas que procedamos con el despacho de la unidad?

</div>

`;



        // Marcadores y ruta

        const coordsOrigen = [-99.1332, 19.4326];

        const coordsDestino = [-99.1676, 19.4270];

        new maplibregl.Marker({ color: "#28a745" }).setLngLat(coordsOrigen).addTo(map);

        new maplibregl.Marker({ color: "#dc3545" }).setLngLat(coordsDestino).addTo(map);

        trazarRuta(coordsOrigen, coordsDestino);

        map.flyTo({ center: [-99.1500, 19.4300], zoom: 13, essential: true });

    };



    // --- NUEVA FUNCIÓN: ACTIVAR TELEMETRÍA ---

    window.activarTelemetria = function () {

        viajeActivo = true;

        const btnViaje = document.getElementById('btn-iniciar-viaje');

        btnViaje.innerText = "En Trayecto...";

        btnViaje.style.background = "#eee";

        btnViaje.disabled = true;


        const chatWindow = document.getElementById('chat-window');

        chatWindow.innerHTML += `

<div class="bot-msg">

<strong>Tracy:</strong> El despacho ha sido autorizado. He iniciado el monitoreo de combustible y progreso para esta unidad. ¡Buen viaje!

</div>

`;

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



    // --- 3. LÓGICA DEL MONITOREO (SIMULACIÓN AUTOMÁTICA) ---

    function updateMini() {

        // Solo simular si el viaje fue activado por el botón

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



    // Lógica del Chat con Gemini

    window.sendMessage = async function () {

        const input = document.getElementById('user-input');

        const chatWindow = document.getElementById('chat-window');

        const message = input.value.trim();

        const API_KEY = "TU_API_KEY_AQUI";



        if (!message) return;



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

            if (data.candidates && data.candidates[0].content.parts[0].text) {

                const botReply = data.candidates[0].content.parts[0].text;

                chatWindow.innerHTML += `<div class="bot-msg"><strong>Tracy:</strong> ${botReply}</div>`;

            }

        } catch (error) {

            chatWindow.innerHTML += `<div class="bot-msg" style="color:red"><strong>Tracy:</strong> Error de conexión.</div>`;

        }

        chatWindow.scrollTop = chatWindow.scrollHeight;

    };

});