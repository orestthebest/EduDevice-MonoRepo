// frontend/src/lib/quiz.js
// Kleine Helfer fürs Quiz, die Lehrer- und Schülerseiten gemeinsam nutzen.
import { m } from '$lib/paraglide/messages.js';

// Getter: Text wird erst beim Zugriff in der aktuellen Sprache geholt
export const TYPE_LABEL = {
	get mc() { return m.quiz_type_mc(); },
	get tf() { return m.quiz_type_tf(); },
	get gap() { return m.quiz_type_gap(); }
};

// Die API legt Wahr/Falsch-Optionen auf Deutsch an -> in der UI in der aktuellen Sprache zeigen
export const optionLabel = (text) => ({ Wahr: m.quiz_true(), Falsch: m.quiz_false() })[text] ?? text;

// "3/4 ist {{0}} und {{1}}." -> [{text:'3/4 ist '}, {gap:0}, {text:' und '}, {gap:1}, {text:'.'}]
export function splitGaps(text) {
	return text
		.split(/\{\{(\d+)\}\}/)
		.map((part, i) => (i % 2 === 1 ? { gap: Number(part) } : { text: part }))
		.filter((p) => p.gap !== undefined || p.text !== '');
}

// Nummern der Lücken im Text, z.B. [0, 1]
export const gapIndexes = (text) => [...new Set([...text.matchAll(/\{\{(\d+)\}\}/g)].map((match) => Number(match[1])))];

export const percent = (score, max) => (max ? Math.round((score / max) * 100) : 0);