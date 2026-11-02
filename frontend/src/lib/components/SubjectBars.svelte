<script>
	// Überblick über alle Fächer als waagrechte Balken.
	//
	// Eine Datenreihe, deshalb eine Farbe und keine Legende — die Fachnamen
	// stehen direkt an den Balken. Die Nulllinie liegt bei 4, weil 4 der
	// kleinstmögliche Wert der Skala ist; eine Achse ab 0 gibt es für Noten
	// nicht. Beide Enden sind beschriftet, damit das klar ist.
	import { SCALE_MIN, SCALE_MAX, scalePos, fmtGrade, standingOf } from '$lib/grades.js';

	let { subjects = [], passMark = 4.6 } = $props();

	const ROW = 44; // Höhe einer Zeile
	const BAR = 20; // Balkenstärke, Obergrenze laut Gestaltungsregel 24px
	const LABEL_W = 150; // Platz für den Fachnamen links
	const VALUE_W = 44; // Platz für die Zahl rechts
	const PAD_R = 8;

	let width = $state(720);
	let plotW = $derived(Math.max(120, width - LABEL_W - VALUE_W - PAD_R));
	let height = $derived(subjects.length * ROW + 26);

	function x(grade) {
		return LABEL_W + scalePos(grade) * plotW;
	}
</script>

<div class="w-full" bind:clientWidth={width}>
	<svg {height} width="100%" viewBox="0 0 {width} {height}" role="img"
		aria-label="Current grade in each subject on a scale from 4 to 10, where 10 is best">
		<!-- Gitternetz: hauchdünn und zurückhaltend -->
		{#each [4, 5, 6, 7, 8, 9, 10] as tick}
			<line x1={x(tick)} y1="0" x2={x(tick)} y2={subjects.length * ROW}
				stroke="var(--color-divider)" stroke-width="1" />
			<text x={x(tick)} y={subjects.length * ROW + 16} text-anchor="middle"
				class="fill-muted text-[11px]">{tick}</text>
		{/each}

		<!-- Bestehensgrenze: eigene Linie mit Beschriftung, nicht nur Farbe -->
		<line x1={x(passMark)} y1="-2" x2={x(passMark)} y2={subjects.length * ROW}
			stroke="var(--color-error)" stroke-width="1" stroke-dasharray="3 3" opacity="0.75" />

		{#each subjects as s, i}
			{@const g = s.current.raw}
			{@const y = i * ROW + (ROW - BAR) / 2}
			{@const st = standingOf(s.standing)}
			<!-- Fachname links, damit die Identität nicht an der Farbe hängt -->
			<text x="0" y={i * ROW + ROW / 2 + 4} class="fill-navy text-[13px]">
				{s.subject_name.length > 20 ? s.subject_name.slice(0, 19) + '…' : s.subject_name}
			</text>

			{#if g != null}
				<!-- Spur -->
				<rect x={LABEL_W} {y} width={plotW} height={BAR} rx="4" fill="var(--color-surface)" />
				<!-- Balken: eckig an der Grundlinie, 4px gerundet am Datenende -->
				<path
					d="M {LABEL_W} {y}
					   H {Math.max(LABEL_W + 4, x(g) - 4)}
					   a 4 4 0 0 1 4 4
					   V {y + BAR - 4}
					   a 4 4 0 0 1 -4 4
					   H {LABEL_W} Z"
					fill="var(--color-blue-violet)" />
				<title>{s.subject_name}: {fmtGrade(g)} ({st.label})</title>

				<!-- Klassenschnitt als Markierung, nur als Aggregat -->
				{#if s.class_comparison}
					<line x1={x(s.class_comparison.class_mean)} y1={y - 3}
						x2={x(s.class_comparison.class_mean)} y2={y + BAR + 3}
						stroke="var(--color-navy)" stroke-width="2" opacity="0.55" />
				{/if}

				<text x={LABEL_W + plotW + 8} y={i * ROW + ROW / 2 + 4}
					class="fill-navy text-[13px] font-semibold">{fmtGrade(g)}</text>
			{:else}
				<text x={LABEL_W} y={i * ROW + ROW / 2 + 4} class="fill-muted text-[12px]">
					not graded yet
				</text>
			{/if}
		{/each}
	</svg>

	<div class="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-subtle">
		<span class="flex items-center gap-1.5">
			<span class="inline-block h-2.5 w-4 rounded-sm bg-blue-violet"></span> your grade
		</span>
		<span class="flex items-center gap-1.5">
			<span class="inline-block h-3.5 w-0.5 bg-navy/55"></span> class average
		</span>
		<span class="flex items-center gap-1.5">
			<span class="inline-block h-3.5 w-0.5 border-l border-dashed border-error"></span>
			pass mark {passMark}
		</span>
		<span>scale {SCALE_MIN}–{SCALE_MAX}, {SCALE_MAX} is best</span>
	</div>
</div>
