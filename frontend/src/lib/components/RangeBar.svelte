<script>
	// Bereich der Endnote auf der Notenskala 4-10.
	//
	// Helles Band: noch möglich (Regeln - alles Offene schlechtestenfalls 4,
	// bestenfalls 10). Dunkles Band: wahrscheinlich (Prognosemodell, 80 %),
	// nur wenn es eine Prognose gibt. Punkt: heutiger Schnitt. Gestrichelt:
	// Bestehensgrenze.
	import { scalePos, fmtGrade } from '$lib/grades.js';

	let { low, high, current, likelyLow = null, likelyHigh = null, passMark = 4.6 } = $props();
	const pos = (g) => `${scalePos(g) * 100}%`;
	// Beschriftung nicht ganz an den Rand, sonst wird sie abgeschnitten
	const label = (g) => `${Math.min(95, Math.max(5, scalePos(g) * 100))}%`;

	// Das dunkle Band bleibt im hellen (die Prognose behauptet nichts, was die Regeln ausschließen)
	let hasLikely = $derived(likelyLow != null && likelyHigh != null);
	let lLow = $derived(hasLikely ? Math.max(low, likelyLow) : null);
	let lHigh = $derived(hasLikely ? Math.min(high, likelyHigh) : null);
	// beschriftet wird das dunkle Band, wenn es eins gibt, sonst das helle
	let a = $derived(hasLikely ? lLow : low);
	let b = $derived(hasLikely ? lHigh : high);

	// Beschriftungen: zuerst die Grenzen des beschrifteten Bandes (fett), dann
	// die des hellen Bandes und 4 / 10 (blass) - nur wo Platz ist
	let labels = $derived.by(() => {
		const out = [];
		const add = (v, text, strong, room = 0.8) => {
			if (out.every((o) => Math.abs(o.v - v) >= Math.max(room, o.room)))
				out.push({ v, text, strong, room });
		};
		if (b - a >= 0.8) {
			add(a, fmtGrade(a), true);
			add(b, fmtGrade(b), true);
		} else {
			add((a + b) / 2, `${fmtGrade(a)} – ${fmtGrade(b)}`, true, 1.4);
		}
		if (hasLikely) {
			add(low, fmtGrade(low), false);
			add(high, fmtGrade(high), false);
		}
		add(4, '4', false, 0.5);
		add(10, '10', false, 0.5);
		return out;
	});
</script>

<div>
	<div
		class="relative h-3 rounded-full bg-surface"
		role="img"
		aria-label="Final grade still possible between {fmtGrade(low)} and {fmtGrade(high)}{hasLikely
			? `, likely between ${fmtGrade(lLow)} and ${fmtGrade(lHigh)}`
			: ''}, today {fmtGrade(current)}"
	>
		<div
			class="absolute inset-y-0 rounded-full bg-blue-violet/20"
			style="left: {pos(low)}; width: max(6px, calc({pos(high)} - {pos(low)}))"
		></div>
		{#if hasLikely}
			<div
				class="absolute inset-y-0 rounded-full bg-blue-violet/55"
				style="left: {pos(lLow)}; width: max(6px, calc({pos(lHigh)} - {pos(lLow)}))"
			></div>
		{/if}
		<div
			class="absolute -inset-y-1 border-l border-dashed border-error/70"
			style="left: {pos(passMark)}"
		></div>
		<div
			class="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-navy"
			style="left: {pos(current)}"
		></div>
	</div>
	<!-- Grenzen direkt am Balken, ohne Überlappung -->
	<div class="relative mt-1 h-4 text-[11px] tabular-nums">
		{#each labels as l}
			<span
				class="absolute -translate-x-1/2 whitespace-nowrap {l.strong
					? 'font-semibold text-navy'
					: 'text-muted'}"
				style="left: {label(l.v)}">{l.text}</span
			>
		{/each}
	</div>
	{#if hasLikely}
		<p class="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-subtle">
			<span class="flex items-center gap-1.5">
				<span class="inline-block h-2 w-4 rounded-full bg-blue-violet/55"></span>likely
			</span>
			<span class="flex items-center gap-1.5">
				<span class="inline-block h-2 w-4 rounded-full bg-blue-violet/20"></span>still possible
			</span>
			<span class="flex items-center gap-1.5">
				<span class="inline-block size-2 rounded-full bg-navy"></span>today
			</span>
			<span class="flex items-center gap-1.5">
				<span class="inline-block h-2.5 border-l border-dashed border-error/70"></span>pass mark
			</span>
		</p>
	{/if}
</div>