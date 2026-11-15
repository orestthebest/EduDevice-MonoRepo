<script>
	// Noch möglicher Bereich der Endnote auf der Notenskala 4-10.
	//
	// Kein Modell: Der Bereich ergibt sich aus den Regeln (fehlende Teile
	// schlechtestenfalls 4, bestenfalls 10). Das Band ist der Bereich, der Punkt
	// der heutige Schnitt, die gestrichelte Linie die Bestehensgrenze.
	import { scalePos, fmtGrade } from '$lib/grades.js';

	let { low, high, current, passMark = 4.6 } = $props();
	const pos = (g) => `${scalePos(g) * 100}%`;
	// Beschriftung nicht ganz an den Rand, sonst wird sie abgeschnitten
	const label = (g) => `${Math.min(95, Math.max(5, scalePos(g) * 100))}%`;
</script>

<div>
	<div
		class="relative h-3 rounded-full bg-surface"
		role="img"
		aria-label="Final grade still possible between {fmtGrade(low)} and {fmtGrade(
			high
		)}, today {fmtGrade(current)}"
	>
		<div
			class="absolute inset-y-0 rounded-full bg-blue-violet/25"
			style="left: {pos(low)}; width: max(6px, calc({pos(high)} - {pos(low)}))"
		></div>
		<div
			class="absolute -inset-y-1 border-l border-dashed border-error/70"
			style="left: {pos(passMark)}"
		></div>
		<div
			class="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-blue-violet"
			style="left: {pos(current)}"
		></div>
	</div>
	<!-- Grenzen des Bereichs direkt am Balken; 4 und 10 nur, wenn kein Wert daneben steht -->
	<div class="relative mt-1 h-4 text-[11px] tabular-nums">
		{#if low > 4.7}<span class="absolute left-0 text-muted">4</span>{/if}
		{#if high < 9.3}<span class="absolute right-0 text-muted">10</span>{/if}
		{#if high - low >= 1}
			<span class="absolute -translate-x-1/2 font-semibold text-navy" style="left: {label(low)}"
				>{fmtGrade(low)}</span
			>
			<span class="absolute -translate-x-1/2 font-semibold text-navy" style="left: {label(high)}"
				>{fmtGrade(high)}</span
			>
		{:else}
			<span
				class="absolute -translate-x-1/2 font-semibold whitespace-nowrap text-navy"
				style="left: {label((low + high) / 2)}">{fmtGrade(low)} – {fmtGrade(high)}</span
			>
		{/if}
	</div>
</div>
