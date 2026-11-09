<script>
	// Die drei Beurteilungskomponenten eines Fachs: Mitarbeit 40 %,
	// Schularbeit 40 %, Projekt 20 %.
	//
	// Jeder Balken ist direkt beschriftet, deshalb genügt eine Farbe — die
	// Identität hängt am Text, nicht am Farbton. Eine Komponente ohne Noten
	// wird ausdrücklich als „noch nicht benotet“ gezeigt und nicht als 0:
	// Würde eine noch nicht geschriebene Schularbeit als Null gewertet, sähe
	// im Oktober die halbe Schule negativ aus.
	import { scalePos, fmtGrade } from '$lib/grades.js';

	let { components = [] } = $props();
</script>

<div class="space-y-2.5">
	{#each components as c}
		<div class="flex items-center gap-3">
			<div class="w-28 shrink-0">
				<span class="text-[13px] font-medium">{c.key}</span>
				<span class="ml-1 text-[11px] text-subtle">{c.label}</span>
			</div>

			<div class="relative h-5 flex-1 overflow-hidden rounded bg-surface">
				{#if c.raw != null}
					<div
						class="h-full rounded-r bg-blue-violet"
						style="width: {Math.max(2, scalePos(c.raw) * 100)}%"
						title="{c.label}: {fmtGrade(c.raw)} from {c.n_marks} mark{c.n_marks === 1 ? '' : 's'}"
					></div>
				{/if}
			</div>

			<div class="w-24 shrink-0 text-right">
				{#if c.raw != null}
					<span class="text-[13px] font-semibold">{fmtGrade(c.raw)}</span>
					<span class="ml-1 text-[11px] text-muted">
						{Math.round(c.weight * 100)}% · {c.n_marks}
					</span>
				{:else}
					<span class="text-[11px] text-muted">not graded yet</span>
				{/if}
			</div>
		</div>
	{/each}
</div>
