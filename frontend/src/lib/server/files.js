import path from 'node:path';
import { env } from '$env/dynamic/private';

// Ordner, in dem alle hochgeladenen Dateien liegen (aus .env, Standard: ./uploads)
// Liegt bewusst NICHT in static/, damit niemand ohne Login Dateien abrufen kann.
export const UPLOAD_DIR = path.resolve(env.UPLOAD_DIR || 'uploads');

// Voller Pfad zu einer gespeicherten Datei.
// path.basename() verhindert, dass jemand mit "../" aus dem Ordner ausbricht.
export function filePath(storedName) {
	return path.join(UPLOAD_DIR, path.basename(storedName));
}