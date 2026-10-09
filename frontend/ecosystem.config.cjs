// PM2-Konfiguration für den EduDevice-Server (172.20.1.115)
// Starten:  pm2 start ecosystem.config.cjs
// Status:   pm2 status      Logs: pm2 logs edudevice-web
//
// Hier stehen KEINE Passwörter (Datei ist im Git).
// Die DB-Zugangsdaten stehen nur in frontend/.env am Server.
module.exports = {
	apps: [
		{
			name: 'edudevice-web',
			script: 'build/index.js',
			cwd: __dirname,
			env: {
				NODE_ENV: 'production',
				PORT: 3000, // 8000 ist für die REST-API reserviert
				HOST: '0.0.0.0', // im Schulnetz/VPN erreichbar
				ORIGIN: 'http://172.20.1.115:3000', // sonst lehnt SvelteKit Formulare (Login) ab
				BODY_SIZE_LIMIT: '50M', // Standard 512 KB ist zu klein für Uploads
				UPLOAD_DIR: '/srv/edudevice/uploads' // Lernmaterialien am Server
			}
		}
	]
};