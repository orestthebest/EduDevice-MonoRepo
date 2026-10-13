// frontend/src/lib/quiz.js
// Kleine Helfer fürs Quiz, die Lehrer- und Schülerseiten gemeinsam nutzen.

export const TYPE_LABEL = {
	mc: 'Multiple choice',
	tf: 'True / False',
	gap: 'Fill in the blanks'
};

// Die API legt Wahr/Falsch-Optionen auf Deutsch an -> in der UI auf Englisch zeigen
export const optionLabel = (text) => ({ Wahr: 'True', Falsch: 'False' })[text] ?? text;

// "3/4 ist {{0}} und {{1}}." -> [{text:'3/4 ist '}, {gap:0}, {text:' und '}, {gap:1}, {text:'.'}]
export function splitGaps(text) {
	return text
		.split(/\{\{(\d+)\}\}/)
		.map((part, i) => (i % 2 === 1 ? { gap: Number(part) } : { text: part }))
		.filter((p) => p.gap !== undefined || p.text !== '');
}

// Nummern der Lücken im Text, z.B. [0, 1]
export const gapIndexes = (text) => [...new Set([...text.matchAll(/\{\{(\d+)\}\}/g)].map((m) => Number(m[1])))];

export const percent = (score, max) => (max ? Math.round((score / max) * 100) : 0);