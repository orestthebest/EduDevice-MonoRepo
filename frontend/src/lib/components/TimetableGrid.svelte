<script>
	import Icon from '$lib/components/Icon.svelte';
	import { PERIODS, subjectColor, shortDate } from '$lib/timetable.js';

	// Wochenraster wie in WebUntis – für die Ansicht (M-3) und die Verwaltung (M-4)
	// days:    [{ key: 'Mo', label: 'Mon', date?: '2026-11-09', off?: { label, note } }]
	// blocks:  Ergebnis von toBlocks(...); block.day passt zu day[dayKey]
	// details: welche Felder unter dem Fachnamen stehen (Schüler: Lehrer, Lehrer: Klasse)
	let {
		days,
		blocks = [],
		dayKey = 'date',
		details = ['room', 'teacher'],
		today = null,
		editable = false,
		onCellClick = () => {},
		onBlockClick = () => {}
	} = $props();

	const PX = 1.4; // Pixel pro Minute
	const toMin = (t) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3, 5));
	const START = toMin(PERIODS[0].start);

	// Ansicht endet nach der letzten belegten Stunde (mind. 6.), Verwaltung zeigt immer alle
	const lastPeriod = $derived(editable ? PERIODS.length : Math.max(6, ...blocks.map((b) => b.to)));
	const periods = $derived(PERIODS.slice(0, lastPeriod));
	const height = $derived((toMin(periods.at(-1).end) - START) * PX);

	const top = (time) => (toMin(time) - START) * PX;
	const span = (from, to) => (toMin(PERIODS[to - 1].end) - toMin(PERIODS[from - 1].start)) * PX;

	// Aktuelle Uhrzeit für die Zeitlinie, jede Minute neu
	let now = $state(new Date());
	$effect(() => {
		const timer = setInterval(() => (now = new Date()), 60_000);
		return () => clearInterval(timer);
	});
	const nowMin = $derived(now.getHours() * 60 + now.getMinutes());
	const showNow = $derived(
		Boolean(today) && days.some((d) => d.date === today) && nowMin >= START && nowMin <= toMin(periods.at(-1).end)
	);

	// Handy: nur ein Tag sichtbar (heute, sonst Montag)
	let picked = $state(null);
	const mobileDay = $derived(picked ?? Math.max(0, days.findIndex((d) => d.date === today)));

	const isToday = (d) => Boolean(d.date) && d.date === today;
	const dayBlocks = (d) => blocks.filter((b) => b.day === d[dayKey]);
</script>

<div class="overflow-hidden rounded-2xl border border-line bg-white">
	<!-- Handy: Tag auswählen -->
	<div class="flex border-b border-line sm:hidden">
		{#each days as d, i (d.key)}
			<button type="button" onclick={() => (picked = i)}
				class="flex-1 cursor-pointer py-2.5 text-sm font-medium transition
				{i === mobileDay ? 'bg-accent-light text-accent-dark' : 'text-subtle hover:text-navy'}">
				{d.label}
			</button>
		{/each}
	</div>

	<div class="grid grid-cols-[3.5rem_minmax(0,1fr)] sm:grid-cols-[3.5rem_repeat(5,minmax(0,1fr))]">
		<!-- Kopfzeile: Wochentage -->
		<div class="border-b border-line"></div>
		{#each days as d, i (d.key)}
			<div class="border-b border-l border-line px-3 py-3 {i === mobileDay ? '' : 'hidden'} sm:block
				{isToday(d) ? 'bg-accent-light/60' : ''}">
				<p class="text-sm font-semibold {isToday(d) ? 'text-accent-dark' : ''}">
					{d.label}
					{#if d.date}<span class="font-normal {isToday(d) ? '' : 'text-subtle'}">{shortDate(d.date)}</span>{/if}
				</p>
			</div>
		{/each}

		<!-- Zeitachse: Stunde + Beginn/Ende -->
		<div class="relative" style="height: {height}px">
			{#each periods as p (p.period)}
				<div class="absolute inset-x-0 pt-1 pr-2 text-right" style="top: {top(p.start)}px">
					<p class="text-xs font-semibold">{p.period}.</p>
					<p class="text-[11px] leading-tight text-subtle tabular-nums">{p.start}</p>
					<p class="text-[11px] leading-tight text-subtle tabular-nums">{p.end}</p>
				</div>
			{/each}
			{#if showNow}
				<span class="absolute right-1 z-20 -translate-y-1/2 rounded-md bg-accent px-1.5 py-0.5 text-[11px] font-semibold text-white tabular-nums"
					style="top: {(nowMin - START) * PX}px">
					{now.toTimeString().slice(0, 5)}
				</span>
			{/if}
		</div>

		<!-- Tagesspalten -->
		{#each days as d, i (d.key)}
			<div class="relative border-l border-line {i === mobileDay ? '' : 'hidden'} sm:block {isToday(d) ? 'bg-accent-light/25' : ''}"
				style="height: {height}px">
				<!-- Hintergrund: Linie pro Stunde, in der Verwaltung klickbare Felder -->
				{#each periods as p (p.period)}
					<div class="absolute inset-x-0 border-t border-divider" style="top: {top(p.start)}px"></div>
					{#if editable && !d.off}
						<button type="button" onclick={() => onCellClick({ day: d, period: p.period })}
							aria-label="Add lesson on {d.label}, period {p.period}"
							class="group absolute inset-x-1 grid cursor-pointer place-items-center rounded-lg border border-dashed border-transparent transition hover:border-accent/50 hover:bg-accent-light/40"
							style="top: {top(p.start) + 2}px; height: {span(p.period, p.period) - 4}px">
							<Icon name="plus" class="size-4 text-accent opacity-0 transition group-hover:opacity-100" />
						</button>
					{/if}
				{/each}

				<!-- Feiertag / Ferien -->
				{#if d.off}
					<div class="absolute inset-1 grid place-items-center rounded-xl bg-surface p-3 text-center">
						<div>
							<Icon name="calendar" class="mx-auto size-5 text-subtle" />
							<p class="mt-2 text-sm font-semibold">{d.off.label ?? 'No lessons'}</p>
							{#if d.off.note}<p class="text-xs text-subtle">{d.off.note}</p>{/if}
						</div>
					</div>
				{/if}

				<!-- Unterrichtsblöcke -->
				{#each dayBlocks(d) as b (b.class_subject_id + '-' + b.from)}
					<svelte:element
						this={editable ? 'button' : 'div'}
						type={editable ? 'button' : undefined}
						onclick={editable ? () => onBlockClick(b) : undefined}
						role={editable ? undefined : 'group'}
						class="absolute z-10 flex overflow-hidden rounded-lg border border-line text-left shadow-sm transition
						{b.cancelled ? 'bg-surface opacity-60' : 'bg-white'}
						{editable ? 'cursor-pointer hover:border-accent hover:shadow-md' : ''}"
						style="top: {top(PERIODS[b.from - 1].start) + 2}px; height: {span(b.from, b.to) - 4}px;
						left: calc({(b.col / b.cols) * 100}% + 4px); width: calc({100 / b.cols}% - 8px)"
					>
						<span class="w-1 shrink-0" style="background: {subjectColor(b.subject)}"></span>
						<span class="min-w-0 flex-1 px-2 py-1.5">
							<span class="block truncate text-sm font-semibold {b.cancelled ? 'line-through' : ''}">{b.subject}</span>
							{#each details as field (field)}
								{#if b[field]}<span class="block truncate text-xs text-subtle">{b[field]}</span>{/if}
							{/each}
							{#if b.cancelled}
								<span class="mt-1 inline-block rounded bg-error/12 px-1.5 py-px text-[10px] font-semibold text-error">Cancelled</span>
							{/if}
						</span>
					</svelte:element>
				{/each}

				<!-- Zeitlinie (jetzt) -->
				{#if showNow && isToday(d)}
					<div class="pointer-events-none absolute inset-x-0 z-20 border-t-2 border-accent" style="top: {(nowMin - START) * PX}px">
						<span class="absolute -top-[5px] -left-[5px] size-2 rounded-full bg-accent"></span>
					</div>
				{/if}
			</div>
		{/each}
	</div>
</div>