<script>
	// Noch möglicher Bereich der Endnote auf der Notenskala 4-10.
	//
	// Kein Modell: Der Bereich ergibt sich aus den Regeln (fehlende Teile
	// schlechtestenfalls 4, bestenfalls 10). Das Band ist der Bereich, der Punkt
	// der heutige Schnitt, die gestrichelte Linie die Bestehensgrenze.
	import { scalePos, fmtGrade } from '$lib/grades.js';

	let { low, high, current, passMark = 4.6 } = $props();
	const pos = (g) => `${scalePos(g) * 100}%`;
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
	<div class="mt-1 flex justify-between text-[11px] text-subtle">
		<span>4</span><span>10</span>
	</div>
</div>
