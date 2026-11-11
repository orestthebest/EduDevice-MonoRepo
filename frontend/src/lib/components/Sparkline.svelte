<script>
	// Kleine Verlaufslinie für eine Fachzeile: der Fachschnitt nach jedem Notentag.
	//
	// Die y-Achse ist in jeder Zeile dieselbe (4 bis 10), damit man die Fächer
	// untereinander vergleichen kann - eine Linie weiter oben ist wirklich besser.
	// Gestrichelt die Bestehensgrenze, der letzte Punkt (der aktuelle Schnitt)
	// ist markiert. Eine Datenreihe, eine Farbe, keine Legende.
	import { scalePos, fmtGrade, shortDate } from '$lib/grades.js';

	let { points = [], passMark = 4.6, width = 120, height = 36 } = $props();

	const PAD = 4; // Platz für den Punkt am Rand
	let plotH = $derived(height - PAD * 2);

	function x(i) {
		return points.length < 2 ? width / 2 : PAD + (i / (points.length - 1)) * (width - PAD * 2);
	}
	function y(grade) {
		return PAD + (1 - scalePos(grade)) * plotH;
	}

	let path = $derived(points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(i)} ${y(p.raw)}`).join(' '));
	let last = $derived(points.at(-1));
	let label = $derived(
		points.length < 2
			? ''
			: `Average went from ${fmtGrade(points[0].raw)} to ${fmtGrade(last.raw)} over ${points.length} grading days`
	);
</script>

{#if points.length >= 2}
	<svg
		{width}
		{height}
		viewBox="0 0 {width} {height}"
		role="img"
		aria-label={label}
		class="overflow-visible"
	>
		<line
			x1="0"
			x2={width}
			y1={y(passMark)}
			y2={y(passMark)}
			stroke="var(--color-error)"
			stroke-width="1"
			stroke-dasharray="2 3"
			opacity="0.5"
		/>
		<path
			d={path}
			fill="none"
			stroke="var(--color-blue-violet)"
			stroke-width="2"
			stroke-linecap="round"
			stroke-linejoin="round"
		/>
		{#each points as p, i}
			<!-- unsichtbare, größere Trefferfläche je Punkt für den Tooltip -->
			<circle cx={x(i)} cy={y(p.raw)} r="6" fill="transparent">
				<title>{shortDate(p.date)}: average {fmtGrade(p.raw)}</title>
			</circle>
		{/each}
		<circle
			cx={x(points.length - 1)}
			cy={y(last.raw)}
			r="3.5"
			fill="var(--color-blue-violet)"
			stroke="white"
			stroke-width="2"
		/>
	</svg>
{:else}
	<span class="text-xs text-muted">too few marks for a trend</span>
{/if}
