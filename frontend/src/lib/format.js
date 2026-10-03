// Dateigröße lesbar machen: 482133 -> "471 KB"
export function formatSize(bytes) {
	if (bytes < 1024) return `${bytes} B`;
	if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
	return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

// Datum lesbar machen: "Today", "Yesterday" oder "24 Sep"
export function formatDate(value) {
	const date = new Date(value);
	const today = new Date();
	const days = Math.floor((today.setHours(0, 0, 0, 0) - new Date(date).setHours(0, 0, 0, 0)) / 86400000);
	if (days === 0) return 'Today';
	if (days === 1) return 'Yesterday';
	return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
}

// Farbe des Datei-Badges je nach Dateityp
export function typeColor(ext) {
	if (ext === 'pdf') return 'bg-error/12 text-error';
	if (['doc', 'docx'].includes(ext)) return 'bg-blue-violet/12 text-blue-violet';
	if (['ppt', 'pptx'].includes(ext)) return 'bg-warning/15 text-[#b4730f]';
	if (['mp4', 'mov', 'webm'].includes(ext)) return 'bg-accent/12 text-accent-dark';
	if (['xls', 'xlsx', 'csv'].includes(ext)) return 'bg-success/12 text-success-dark';
	return 'bg-surface text-subtle';
}