<script>
	// Notenentwicklung über die drei Trimester, eine Linie je Fach.
	//
	// Eine Datenreihe, deshalb keine Legende und eine Farbe. Jeder Punkt trägt
	// seinen Wert als Beschriftung, damit nichts nur im Tooltip steht.
	//
	// Gezeigt werden Mitarbeit und Schularbeit je Trimester. Das Projekt fehlt
	// hier bewusst: Es wird laut Notenordnung einmal für das ganze Jahr
	// beurteilt und gehört damit in keinen einzelnen Zeitabschnitt.
	import { scalePos, fmtGrade } from '$lib/grades.js';

	let { points = [], passMark = 4.6, height = 132 } = $props();

	// INSET hält den ersten und letzten Punkt von der Achse weg, sonst ragt
	// deren Wertbeschriftung über den Rand des Diagramms hinaus.
	const PAD_L = 32, PAD_R = 34, PAD_T = 18, PAD_B = 24, INSET = 12;
	let width = $state(420);

	let graded = $derived(points.filter((p) => p.raw != null));
	let plotW = $derived(Math.max(60, width - PAD_L - PAD_R - INSET * 2));
	let plotH = $derived(height - PAD_T - PAD_B);

	function x(i) {
		return PAD_L + INSET + (points.length < 2 ? plotW / 2 : (i / (points.length - 1)) * plotW);
	}
	function y(grade) {
		return PAD_T + (1 - scalePos(grade)) * plotH;
	}
	let path = $derived(
		points
			.map((p, i) => (p.raw == null ? null : `${x(i)},${y(p.raw)}`))
			.filter(Boolean)
			.map((c, i) => (i === 0 ? `M ${c}` : `L ${c}`))
			.join(' ')
	);
</script>

<div class="w-full" bind:clientWidth={width}>
	{#if graded.length === 0}
		<p class="py-6 text-center text-xs text-muted">No marks in any trimester yet</p>
	{:else}
		<svg {height} width="100%" viewBox="0 0 {width} {height}" role="img"
			aria-label="Grade development across the trimesters">
			<!-- waagrechte Hilfslinien bei 4, 7 und 10 -->
			{#each [4, 7, 10] as tick}
				<line x1={PAD_L} y1={y(tick)} x2={width - PAD_R} y2={y(tick)}
					stroke="var(--color-divider)" stroke-width="1" />
				<text x={PAD_L - 6} y={y(tick) + 4} text-anchor="end" class="fill-muted text-[10px]">
					{tick}
				</text>
			{/each}

			<!-- Bestehensgrenze, am rechten Ende beschriftet, damit die Linie
			     auch ohne die Legende des Übersichtsdiagramms lesbar ist -->
			<line x1={PAD_L} y1={y(passMark)} x2={width - PAD_R} y2={y(passMark)}
				stroke="var(--color-error)" stroke-width="1" stroke-dasharray="3 3" opacity="0.7" />
			<text x={width - PAD_R + 4} y={y(passMark) + 3.5} class="fill-error text-[10px]">
				{passMark}
			</text>

			<path d={path} fill="none" stroke="var(--color-blue-violet)" stroke-width="2"
				stroke-linecap="round" stroke-linejoin="round" />

			{#each points as p, i}
				{#if p.raw != null}
					<!-- 2px Ring in Flächenfarbe, damit sich Punkt und Linie trennen -->
					<circle cx={x(i)} cy={y(p.raw)} r="5"
						fill="var(--color-blue-violet)" stroke="white" stroke-width="2" />
					<text x={x(i)} y={y(p.raw) - 10} text-anchor="middle"
						class="fill-navy text-[11px] font-medium">{fmtGrade(p.raw, 1)}</text>
					<title>Trimester {p.trimester}: {fmtGrade(p.raw)} ({p.n_marks} marks)</title>
				{/if}
				<text x={x(i)} y={height - 6} text-anchor="middle" class="fill-muted text-[10px]">
					T{p.trimester}
				</text>
			{/each}
		</svg>
	{/if}
</div>
