<script>
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import TimetableGrid from '$lib/components/TimetableGrid.svelte';
	import { toBlocks, weekDays, weekStart, addDays, shortDate } from '$lib/timetable.js';
	import { todayISO } from '$lib/format.js';

	let { data } = $props();

	const today = todayISO();

	// school_calendar.day_type -> Anzeige im Tagesfeld
	const OFF_LABEL = {
		holiday: 'Public holiday',
		break: 'School break',
		autonomous_day: 'No school',
		info: 'No lessons'
	};

	const days = $derived(
		weekDays(data.monday).map((d) => {
			const off = data.timetable.days_off?.find((o) => o.date === d.date);
			return off ? { ...d, off: { label: OFF_LABEL[off.day_type] ?? 'No lessons', note: off.note } } : d;
		})
	);
	const blocks = $derived(toBlocks(data.timetable.lessons));

	// Schüler sehen die Lehrkraft, Lehrkräfte die Klasse
	const details = $derived(data.role === 'lehrkraft' ? ['class_name', 'room'] : ['room', 'teacher']);

	const isThisWeek = $derived(data.monday === weekStart(today));
	const range = $derived(`${shortDate(data.monday)} – ${shortDate(addDays(data.monday, 4))}${data.monday.slice(0, 4)}`);
</script>

<svelte:head>
	<title>Timetable · EduDevice</title>
</svelte:head>

<PageHeader title="Timetable" subtitle={isThisWeek ? `This week · ${range}` : `Week ${range}`}>
	<div class="flex items-center gap-2">
		<a href="?week={addDays(data.monday, -7)}" aria-label="Previous week"
			class="grid size-10 place-items-center rounded-xl border border-line bg-white transition hover:border-accent hover:text-accent-dark">
			<Icon name="back" />
		</a>
		{#if !isThisWeek}
			<a href="/timetable"
				class="rounded-xl border border-line bg-white px-4 py-2.5 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
				Today
			</a>
		{/if}
		<a href="?week={addDays(data.monday, 7)}" aria-label="Next week"
			class="grid size-10 place-items-center rounded-xl border border-line bg-white transition hover:border-accent hover:text-accent-dark">
			<Icon name="next" />
		</a>
	</div>
</PageHeader>

{#if data.mock}
	<p class="mb-4 rounded-lg border border-warning/40 bg-warning/10 px-4 py-2.5 text-sm">
		Demo data – the real timetable appears as soon as the API is connected.
	</p>
{/if}

{#if data.timetable.lessons.length === 0 && days.every((d) => !d.off)}
	<p class="mb-4 rounded-lg bg-surface px-4 py-3 text-sm text-subtle">No lessons this week.</p>
{/if}

<TimetableGrid {days} {blocks} {details} {today} />