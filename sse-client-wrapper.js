const http = require('http');
const https = require('https');

const sseUrl = process.argv[2];
if (!sseUrl) {
    console.error('Usage: node sse-client-wrapper.js <sse-url>');
    process.exit(1);
}

const urlObj = new URL(sseUrl);
const client = urlObj.protocol === 'https:' ? https : http;

let sessionId = null;
let messagesUrl = null;
let isConnected = false;

// SSE-Verbindung mit nativem HTTP
function connectSSE() {
    const req = client.request(sseUrl, {
        headers: {
            'Accept': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'User-Agent': 'Mozilla/5.0'
        }
    }, (res) => {
        // Entferne Debug-Output für Claude Desktop
        // console.error('SSE connected, status:', res.statusCode);
        // console.error('Response headers:', res.headers);
        let buffer = '';

        res.on('data', (chunk) => {
            const chunkStr = chunk.toString();
            // Entferne Debug-Output
            // if (!chunkStr.startsWith(': ping')) {
            //     console.error('Received chunk:', JSON.stringify(chunkStr));
            // }
            buffer += chunkStr;
            // Unterstütze sowohl \n\n als auch \r\n\r\n
            const blocks = buffer.split(/\r?\n\r?\n/);
            buffer = blocks.pop();

            blocks.forEach(eventBlock => {
                if (!eventBlock.trim()) return;

                const lines = eventBlock.split(/\r?\n/);
                let eventType = 'message';
                let data = '';

                lines.forEach(line => {
                    if (line.startsWith('event: ')) {
                        eventType = line.substring(7).trim();
                    } else if (line.startsWith('data: ')) {
                        data += line.substring(6);
                    } else if (line.startsWith(': ')) {
                        // Kommentar/Ping - ignorieren
                    }
                });

                if (eventType === 'endpoint' && data) {
                    const match = data.match(/session_id=([^&]+)/);
                    if (match) {
                        sessionId = match[1];
                        messagesUrl = `${urlObj.protocol}//${urlObj.host}${data}`;
                        isConnected = true;
                        // console.error('Connected to MCP server, session:', sessionId);
                        // console.error('Messages URL:', messagesUrl);
                    }
                } else if (data && isConnected) {
                    // MCP-Antwort über SSE empfangen
                    try {
                        // Direkt ausgeben ohne zusätzliches JSON.stringify
                        console.log(data);
                    } catch (e) {
                        console.error('Parse error:', e);
                    }
                }
            });
        });

        res.on('end', () => {
            // console.error('SSE connection closed, reconnecting...');
            setTimeout(connectSSE, 1000);
        });

        res.on('error', (error) => {
            // console.error('Response error:', error);
        });
    });

    req.on('error', (error) => {
        // console.error('Connection error:', error);
        setTimeout(connectSSE, 1000);
    });

    req.end();
}

// Starte SSE-Verbindung
connectSSE();

// Verhindere Prozess-Beendigung bei Fehlern
process.on('uncaughtException', (err) => {
    // Stille Fehlerbehandlung für Claude Desktop
});

process.on('unhandledRejection', (err) => {
    // Stille Fehlerbehandlung für Claude Desktop
});

// stdin lesen für ausgehende MCP-Anfragen
let stdinBuffer = '';
process.stdin.on('data', (chunk) => {
    stdinBuffer += chunk.toString();
    const lines = stdinBuffer.split('\n');
    stdinBuffer = lines.pop();

    lines.forEach(line => {
        line = line.trim(); // Entferne Whitespace
        if (line && messagesUrl && isConnected) {
            // Validiere dass es JSON ist
            try {
                JSON.parse(line);
            } catch (e) {
                // console.error('Invalid JSON, skipping:', line);
                return;
            }

            const postUrlObj = new URL(messagesUrl);
            const postClient = postUrlObj.protocol === 'https:' ? https : http;

            const postReq = postClient.request(messagesUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Content-Length': Buffer.byteLength(line)
                }
            }, (postRes) => {
                let data = '';
                postRes.on('data', chunk => data += chunk);
                postRes.on('end', () => {
                    // POST antwortet nur mit "Accepted" - Antwort kommt über SSE
                });
            });

            postReq.on('error', (error) => {
                // Stille Fehlerbehandlung
            });

            postReq.write(line);
            postReq.end();
        }
    });
});

// Keep-alive - Prozess läuft weiter
process.stdin.resume(); // Verhindert, dass der Prozess sich beendet

// Entferne Waiting-Ausgabe
// setInterval(() => {
//     if (!isConnected) {
//         console.error('Waiting for connection...');
//     }
// }, 30000);