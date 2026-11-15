<script>
	// Der Fachschnitt im Lauf des Schuljahres.
	//
	// Die Linie ist der Schnitt nach jedem Notentag - so viel hat sich die Note
	// bewegt, nicht nur der Stand am Trimesterende. Die blassen Punkte dahinter
	// sind die einzelnen Noten, damit man sieht, woher die Bewegung kommt.
	// x-Achse: das ganze Jahr, die Trimester als Bänder, keine Datumsangaben;
	// die Strichlinie "today" zeigt, wie viel vom Jahr schon vorbei ist.
	import { scalePos, fmtGrade } from '$lib/grades.js';

	let {
		progression = [],
		marks = [],
		trimesters = [],
		today,
		passMark = 4.6,
		height = 150
	} = $props();

	const PAD_L = 24,
		PAD_R = 30,
		PAD_T = 10,
		PAD_B = 22;
	let width = $state(420);

	const day = (iso) => new Date(iso + 'T00:00:00').getTime();
	let start = $derived(
		trimesters.length ? day(trimesters[0].start) : day(progression[0]?.date ?? today)
	);
	let end = $derived(trimesters.length ? day(trimesters.at(-1).end) : day(today));
	let plotW = $derived(Math.max(60, width - PAD_L - PAD_R));
	let plotH = $derived(height - PAD_T - PAD_B);

	function x(iso) {
		const t = Math.min(Math.max(day(iso), start), end);
		return PAD_L + (end > start ? (t - start) / (end - start) : 0.5) * plotW;
	}
	function y(grade) {
		return PAD_T + (1 - scalePos(grade)) * plotH;
	}

	let path = $derived(
		progression.map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(p.date)} ${y(p.raw)}`).join(' ')
	);
	let last = $derived(progression.at(-1));
	let showToday = $derived(today && day(today) > start && day(today) < end);
	let label = $derived.by(() => {
		if (!progression.length) return '';
		const values = progression.map((p) => p.raw);
		return (
			`Average over the year: from ${fmtGrade(values[0])} to ${fmtGrade(last.raw)} now, ` +
			`lowest ${fmtGrade(Math.min(...values))}, highest ${fmtGrade(Math.max(...values))}`
		);
	});
</script>

<div class="w-full" bind:clientWidth={width}>
	{#if progression.length === 0}
		<p class="py-6 text-center text-xs text-muted">No marks yet</p>
	{:else}
		<svg {height} width="100%" viewBox="0 0 {width} {height}" role="img" aria-label={label}>
			<!-- Trimester als Bänder; das mittlere hinterlegt, damit die Grenzen sichtbar sind -->
			{#each trimesters as t, i}
				{#if i % 2 === 1}
					<rect
						x={x(t.start)}
						y={PAD_T}
						width={x(t.end) - x(t.start)}
						height={plotH}
						fill="var(--color-surface)"
					/>
				{/if}
				<text
					x={(x(t.start) + x(t.end)) / 2}
					y={height - 6}
					text-anchor="middle"
					class="fill-muted text-[10px]">T{t.number}</text
				>
			{/each}

			<!-- waagrechte Hilfslinien bei 4, 7 und 10 -->
			{#each [4, 7, 10] as tick}
				<line
					x1={PAD_L}
					y1={y(tick)}
					x2={width - PAD_R}
					y2={y(tick)}
					stroke="var(--color-divider)"
					stroke-width="1"
				/>
				<text x={PAD_L - 6} y={y(tick) + 3.5} text-anchor="end" class="fill-muted text-[10px]"
					>{tick}</text
				>
			{/each}

			<!-- Bestehensgrenze -->
			<line
				x1={PAD_L}
				y1={y(passMark)}
				x2={width - PAD_R}
				y2={y(passMark)}
				stroke="var(--color-error)"
				stroke-width="1"
				stroke-dasharray="3 3"
				opacity="0.7"
			/>
			<text x={width - PAD_R + 4} y={y(passMark) + 3.5} class="fill-error text-[10px]"
				>{passMark}</text
			>

			{#if showToday}
				<line
					x1={x(today)}
					y1={PAD_T}
					x2={x(today)}
					y2={PAD_T + plotH}
					stroke="var(--color-muted)"
					stroke-width="1"
					stroke-dasharray="2 3"
				/>
				<text x={x(today) + 4} y={PAD_T + 9} class="fill-muted text-[10px]">today</text>
			{/if}

			<!-- einzelne Noten, blass -->
			{#each marks as m}
				<circle
					cx={x(m.date)}
					cy={y(m.value)}
					r="2.5"
					fill="var(--color-blue-violet)"
					opacity="0.25"
				></circle>
			{/each}

			<!-- der Schnitt nach jedem Notentag -->
			<path
				d={path}
				fill="none"
				stroke="var(--color-blue-violet)"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
			/>
			<circle
				cx={x(last.date)}
				cy={y(last.raw)}
				r="4.5"
				fill="var(--color-blue-violet)"
				stroke="white"
				stroke-width="2"
			>
				<title>Now: {fmtGrade(last.raw)}</title>
			</circle>
		</svg>
	{/if}
</div>