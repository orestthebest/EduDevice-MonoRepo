import path from 'node:path';
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import { env } from '$env/dynamic/private';

// Ordner, in dem alle hochgeladenen Dateien liegen (aus .env, Standard: ./uploads)
// Liegt bewusst NICHT in static/, damit niemand ohne Login Dateien abrufen kann.
export const UPLOAD_DIR = path.resolve(env.UPLOAD_DIR || 'uploads');

// Voller Pfad zu einer gespeicherten Datei.
// path.basename() verhindert, dass jemand mit "../" aus dem Ordner ausbricht.
export function filePath(storedName) {
	return path.join(UPLOAD_DIR, path.basename(storedName));
}

// Erlaubte Dateitypen und maximale Größe für Uploads
export const ALLOWED_EXTENSIONS = ['pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'txt', 'png', 'jpg', 'jpeg', 'mp4', 'zip'];
export const MAX_SIZE = 50 * 1024 * 1024; // 50 MB

// Dateiendung aus dem Originalnamen holen: "SQL Joins.PDF" -> "pdf"
export function getExtension(filename) {
	return path.extname(filename).slice(1).toLowerCase();
}

// Hochgeladene Datei im uploads-Ordner speichern.
// Zufälliger Name (UUID), damit nichts überschrieben wird und niemand Namen erraten kann.
export async function saveFile(file) {
	const storedName = `${crypto.randomUUID()}.${getExtension(file.name)}`;
	await fs.mkdir(UPLOAD_DIR, { recursive: true }); // Ordner anlegen, falls er fehlt
	await fs.writeFile(filePath(storedName), Buffer.from(await file.arrayBuffer()));
	return storedName;
}

// Datei aus dem uploads-Ordner löschen (Fehler ignorieren, falls sie schon weg ist)
export async function deleteFile(storedName) {
	await fs.rm(filePath(storedName), { force: true });
}