<script>
	// Fehlzeiten in einem Fach als Budget: wie viel vom Jahr schon versäumt ist,
	// wohin es im aktuellen Tempo geht, und wo die Grenzen liegen
	// (20 % = Prüfung nötig, 30 % = nicht beurteilbar).
	//
	// Ein Balken, eine Datenreihe: gefüllt = schon versäumt, Umriss = Hochrechnung.
	// Die Grenzen sind direkt beschriftet; darunter nur zwei kurze Zeilen.
	let { absence } = $props();

	const SCALE_MAX = 0.35; // Achse bis 35 %, damit die 30-%-Grenze sichtbar Luft hat

	function pos(rate) {
		return `${(Math.min(rate, SCALE_MAX) / SCALE_MAX) * 100}%`;
	}
	function pct(rate, digits = 1) {
		return `${(rate * 100).toFixed(digits).replace(/\.0$/, '')} %`;
	}
	const fmt = (n) => n.toLocaleString('en-GB');

	let missed = $derived(fmt(absence.missed_minutes));
	let total = $derived(fmt(absence.total_minutes));
	let lessonsLeft = $derived(
		absence.lesson_minutes
			? Math.floor(absence.minutes_left_before_exam / absence.lesson_minutes)
			: null
	);
</script>

<div>
	<div
		class="relative h-3 rounded-full bg-surface"
		role="img"
		aria-label="Missed {pct(absence.rate)} of the year's lessons{absence.projected_rate != null
			? `, heading for ${pct(absence.projected_rate)}`
			: ''}. Exam required from 20 %, not assessable from 30 %."
	>
		{#if absence.projected_rate != null && absence.projected_rate > absence.rate}
			<div
				class="absolute inset-y-0 left-0 rounded-full border border-dashed border-blue-violet/60"
				style="width: {pos(absence.projected_rate)}"
			></div>
		{/if}
		<div
			class="absolute inset-y-0 left-0 rounded-full bg-blue-violet"
			style="width: max(4px, {pos(absence.rate)})"
		></div>
		{#each [[0.2, 'bg-warning'], [0.3, 'bg-error']] as [limit, color]}
			<div class="absolute -inset-y-1 w-0.5 {color}" style="left: {pos(limit)}"></div>
		{/each}
	</div>
	<div class="relative mt-1 h-4 text-[11px] text-subtle">
		<span class="absolute -translate-x-1/2" style="left: {pos(0.2)}">20 % exam</span>
		<span class="absolute -translate-x-1/2" style="left: {pos(0.3)}">30 %</span>
	</div>
	{#if absence.projected_rate != null && absence.projected_rate > absence.rate}
		<p class="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-subtle">
			<span class="flex items-center gap-1.5">
				<span class="inline-block h-2 w-4 rounded-full bg-blue-violet"></span>missed so far
			</span>
			<span class="flex items-center gap-1.5">
				<span class="inline-block h-2 w-4 rounded-full border border-dashed border-blue-violet/60"
				></span>
				at this pace: {pct(absence.projected_rate, 0)} by year end
			</span>
		</p>
	{/if}
	<p class="mt-2 text-sm">
		Missed <strong class="tabular-nums">{missed}</strong> / {total} min ({pct(absence.rate)})
	</p>
	<p class="text-sm text-subtle">
		{#if absence.status === 'not_assessable'}
			Over 30 % — can no longer be graded normally
		{:else if absence.status === 'exam_required'}
			Over 20 % — an extra exam is required
		{:else}
			<strong class="text-navy tabular-nums">{fmt(absence.minutes_left_before_exam)}</strong> more
			min{#if lessonsLeft != null}&nbsp;(≈ {lessonsLeft} lessons){/if} before an extra exam
		{/if}
	</p>
	{#if absence.unknown_late}
		<p class="mt-1 text-xs text-muted">
			+ {absence.unknown_late} late arrival{absence.unknown_late === 1 ? '' : 's'} without minutes (not
			counted)
		</p>
	{/if}
</div>