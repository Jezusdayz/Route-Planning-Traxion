document.addEventListener('DOMContentLoaded', function() {
    const map = new maplibregl.Map({
        container: 'mapa', 
        
        style: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json', 
        center: [-99.1332, 19.4326], 
        zoom: 12,
        trackResize: true
    });

    map.addControl(new maplibregl.NavigationControl());

    
    map.on('load', () => {
        map.resize();
    });
});