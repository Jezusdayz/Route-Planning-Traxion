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
        const form = document.getElementById('setup-form');
        const chat = document.getElementById('chat-container');
        const origin = document.getElementById('route-origin').value;
        const dest = document.getElementById('route-dest').value;
        
        if(!origin || !dest) {
            alert("Por favor completa los campos de ruta.");
            return;
        }
        form.style.display = 'none';
        chat.style.display = 'flex';
        console.log(`Tracy configurada: ${origin} a ${dest}`);
    };

    window.sendMessage = async function() {
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
            const botReply = data.candidates[0].content.parts[0].text;
            chatWindow.innerHTML += `<div class="bot-msg"><strong>Tracy:</strong> ${botReply}</div>`;
        } catch (error) {
            chatWindow.innerHTML += `<div class="bot-msg" style="color:red">Error de conexión.</div>`;
        }
        chatWindow.scrollTop = chatWindow.scrollHeight;
    };

    // --- 3. LÓGICA DEL MONITOREO ---
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
            if(fuelVal < 20) fBar.style.background = "#dc3545";
        }

        if(dBar && dVal && distance < totalDist) {
            distance += 0.05;
            dVal.innerText = distance.toFixed(1);
            dBar.style.width = ((distance / totalDist) * 100) + "%";
        }
    }
    setInterval(updateMini, 2000);
});