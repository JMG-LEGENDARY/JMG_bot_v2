// TANT QUE TU ES SUR TON PC DE DEV : 
// Utilise l'IP Tailscale de ta machine Debian (celle du bot) ou localhost avec le tunnel SSH !
const SERVER_IP = "127.0.0.1"; 
const WS_URL = `ws://${SERVER_IP}:8000/api/v1/live`;

// Initialisation des icônes Lucide
lucide.createIcons();

// --- CONFIGURATION DU GRAPHIQUE FUTURISTE (Chart.js) ---
const ctx = document.getElementById('pingChart').getContext('2d');
const maxDataPoints = 60; // 60 points à 0.5s d'intervalle = 30 secondes d'historique visible

const pingChart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: Array(maxDataPoints).fill(''), // Pré-remplir les labels pour éviter les saccades
        datasets: [
            {
                label: 'Event Loop (Réactivité Interne)',
                data: Array(maxDataPoints).fill(0),
                borderColor: '#00b4d8',
                borderWidth: 2,
                pointRadius: 0,
                backgroundColor: 'rgba(0, 180, 216, 0.05)',
                fill: true,
                tension: 0.4 
            },
            {
                label: 'Discord Ping (Gateway)',
                data: Array(maxDataPoints).fill(0),
                borderColor: 'rgba(114, 137, 218, 0.4)', // Couleur Discord semi-transparente
                borderWidth: 1.5,
                borderDash: [4, 4], // Ligne pointillée car mise à jour moins fréquente
                pointRadius: 0,
                fill: false,
                tension: 0.2
            }
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false, // Désactive les animations pour une réactivité brute à 0.5s
        plugins: { legend: { display: false } },
        scales: {
            x: { display: false },
            y: {
                min: 0,
                suggestedMax: 10, // 👈 Si le ping reste bas, l'échelle se bloque à 10ms max. Les variations de 0.04 à 2ms vont faire de vraies vagues !
                grid: { color: 'rgba(255, 255, 255, 0.03)' },
                ticks: { color: '#8a99ad', font: { size: 10 } }
                }
        }
    }
});

// --- CONNEXION WEBSOCKET EN TEMPS RÉEL ---
function connectMonitoringWS() {
    console.log(`Tentative de connexion au flux live : ${WS_URL}`);
    const socket = new WebSocket(WS_URL);

    socket.onopen = () => {
        console.log("Connecté au Backend JMG_BOT v2");
        updateGlobalStatusDot("stable");
    };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateDashboard(data);
    };

    socket.onclose = () => {
        console.log("Connexion perdue. Reconnexion dans 4 secondes...");
        updateGlobalStatusDot("offline");
        setTimeout(connectMonitoringWS, 4000);
    };

    socket.onerror = (error) => {
        console.error("Erreur WebSocket :", error);
        socket.close();
    };
}

// --- GESTION DU VOYANT GLOBAL DE SANTÉ ---
function updateGlobalStatusDot(health) {
    const dot = document.getElementById('global-status-dot');
    const text = document.getElementById('global-status-text');
    if (!dot || !text) return;

    switch(health) {
        case "stable":
            dot.className = "status-dot online";
            text.innerText = "Live Synced";
            text.style.color = "#00ffaa";
            break;
        case "lagging":
            dot.className = "status-dot warning"; // Assure-toi d'avoir une classe .warning en CSS (orange)
            text.innerText = "Loop Lagging";
            text.style.color = "#ffaa00";
            break;
        case "unresponsive":
            dot.className = "status-dot critical";
            text.innerText = "Unresponsive";
            text.style.color = "#ff3366";
            break;
        case "offline":
        default:
            dot.className = "status-dot offline";
            text.innerText = "Déconnecté";
            text.style.color = "#ff3366";
            break;
    }
}

// --- MISE À JOUR DE L'INTERFACE ---
function updateDashboard(data) {
    // 1. Mise à jour de la santé globale visuelle
    updateGlobalStatusDot(data.bot.health);

    // 2. Section Latences (Affichage de la latence interne en priorité)
    const loopPing = data.bot.loop_latency_ms;
    const discordPing = data.bot.discord_latency_ms;
    
    // On affiche la latence de la boucle d'événements, représentative de la vitesse à 0.5s
    document.getElementById('bot-ping').innerHTML = `${loopPing} <span style="font-size: 1.2rem; color: var(--text-secondary)">ms (loop)</span>`;
    
    // Optionnel : Si tu as un élément pour afficher le ping Discord à côté, tu peux l'ajouter,
    // sinon l'uptime reste en dessous
    const uptimeSec = data.bot.uptime_seconds;
    const hrs = Math.floor(uptimeSec / 3600);
    const mins = Math.floor((uptimeSec % 3600) / 60);
    document.getElementById('bot-uptime').innerText = `Discord: ${discordPing}ms | Uptime: ${hrs}h ${mins}m`;

    // 3. Section Minecraft Server
    const stateElement = document.getElementById('mc-state');
    const stateStr = data.minecraft_server.state;
    stateElement.innerText = stateStr.toUpperCase();
    
    if(stateStr === 'online') stateElement.style.color = "#00ffaa";
    else if(stateStr === 'crash') stateElement.style.color = "#ff3366";
    else stateElement.style.color = "#8a99ad";

    document.getElementById('mc-players-count').innerText = `Joueurs en ligne : ${data.minecraft_server.online_players_count}`;

    // 4. Spécificités Hardware
    document.getElementById('sys-ram').innerHTML = `${data.bot.memory_mb} <span style="font-size: 1.2rem;">Mo</span>`;
    document.getElementById('sys-cpu').innerText = `Charge CPU: ${data.bot.cpu_percent}%`;

    // 5. Flux des événements (Logs récents)
    const logList = document.getElementById('events-log');
    logList.innerHTML = ""; 
    if(data.minecraft_server.last_events.length === 0) {
        logList.innerHTML = `<li style="color: var(--text-secondary)">Aucun événement récent</li>`;
    } else {
        data.minecraft_server.last_events.forEach(event => {
            const li = document.createElement('li');
            li.className = "event-item";
            li.innerText = event;
            logList.appendChild(li);
        });
    }

    // 6. Injection des deux métriques dans le graphique et adaptation de la couleur
    appendChartData(loopPing, discordPing, data.bot.health);
}

function appendChartData(loopValue, discordValue, health) {
    const loopDataset = pingChart.data.datasets[0];
    const discordDataset = pingChart.data.datasets[1];

    // Décalage des données vers la gauche
    loopDataset.data.shift();
    loopDataset.data.push(loopValue);

    discordDataset.data.shift();
    discordDataset.data.push(discordValue);

    // 🎨 Adaptation dynamique de la couleur du graphique selon la charge
    if (health === "unresponsive") {
        loopDataset.borderColor = "#ff3366"; // Rouge critique
        loopDataset.backgroundColor = 'rgba(255, 51, 102, 0.05)';
    } else if (health === "lagging") {
        loopDataset.borderColor = "#ffaa00"; // Orange surcharge mini-jeux / crafty
        loopDataset.backgroundColor = 'rgba(255, 170, 0, 0.05)';
    } else {
        loopDataset.borderColor = "#00b4d8"; // Bleu stable cyber
        loopDataset.backgroundColor = 'rgba(0, 180, 216, 0.05)';
    }

    pingChart.update('none'); // Rafraîchissement ultra-rapide sans ré-allocation mémoire
}

// Lancement automatique du flux au chargement de la page
connectMonitoringWS();