<script>
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import TimetableGrid from '$lib/components/TimetableGrid.svelte';
	import { toBlocks, weekDays, weekStart, addDays, shortDate, periodOf } from '$lib/timetable.js';
	import { todayISO } from '$lib/format.js';
	import { m } from '$lib/paraglide/messages.js';

	let { data } = $props();

	const today = todayISO();

	// school_calendar.day_type -> Anzeige im Tagesfeld
	const OFF_LABEL = {
		holiday: m.tt_holiday(),
		break: m.tt_break(),
		autonomous_day: m.tt_no_school(),
		info: m.tt_no_lessons()
	};

	const WEEKDAY_NAME = { Mo: m.wd_monday(), Di: m.wd_tuesday(), Mi: m.wd_wednesday(), Do: m.wd_thursday(), Fr: m.wd_friday() };

	// Schulkalender der Woche: freie Tage (has_lessons = false) füllen die ganze Spalte,
	// an anderen Tagen nur ein Hinweis im Tageskopf (getauschter Stundenplan, Sprechtag, ...)
	const days = $derived(
		weekDays(data.monday).map((d) => {
			const entry = data.timetable.calendar?.find((c) => c.date === d.date);
			if (!entry) return d;
			if (!entry.has_lessons) {
				return { ...d, off: { label: OFF_LABEL[entry.day_type] ?? m.tt_no_lessons(), note: entry.note } };
			}
			const note = entry.day_type === 'swapped_timetable' && entry.timetable_weekday
				? m.tt_swapped({ day: WEEKDAY_NAME[entry.timetable_weekday] })
				: entry.note;
			return { ...d, note };
		})
	);

	// Alte Stunden außerhalb des Rasters (period = null) passen nicht ins Raster -> Hinweis statt stillschweigend weglassen
	const outside = $derived(data.timetable.lessons.filter((l) => !(l.period ?? periodOf(l.start_time))).length);
	const blocks = $derived(toBlocks(data.timetable.lessons));

	// Schüler sehen die Lehrkraft, Lehrkräfte die Klasse
	const details = $derived(data.role === 'lehrkraft' ? ['class_name', 'room'] : ['room', 'teacher']);

	const isThisWeek = $derived(data.monday === weekStart(today));
	const range = $derived(`${shortDate(data.monday)} – ${shortDate(addDays(data.monday, 4))}${data.monday.slice(0, 4)}`);
</script>

<svelte:head>
	<title>{m.nav_timetable()} · EduDevice</title>
</svelte:head>

<PageHeader title={m.nav_timetable()} subtitle={isThisWeek ? m.tt_this_week({ range }) : m.tt_week({ range })}>
	<div class="flex items-center gap-2">
		<a href="?week={addDays(data.monday, -7)}" aria-label={m.tt_prev_week()}
			class="grid size-8 place-items-center rounded-lg border border-line bg-white transition hover:border-accent hover:text-accent-dark">
			<Icon name="back" />
		</a>
		{#if !isThisWeek}
			<a href="/timetable"
				class="inline-flex h-8 items-center rounded-lg border border-line bg-white px-3 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
				{m.date_today()}
			</a>
		{/if}
		<a href="?week={addDays(data.monday, 7)}" aria-label={m.tt_next_week()}
			class="grid size-8 place-items-center rounded-lg border border-line bg-white transition hover:border-accent hover:text-accent-dark">
			<Icon name="next" />
		</a>
	</div>
</PageHeader>

{#if data.mock}
	<p class="mb-4 rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-sm">
		{m.tt_demo_view()}
	</p>
{/if}

{#if data.timetable.lessons.length === 0 && days.every((d) => !d.off)}
	<p class="mb-4 rounded-lg bg-surface px-3 py-2 text-sm text-subtle">{m.tt_none_week()}</p>
{/if}

{#if outside > 0}
	<p class="mb-4 rounded-lg bg-surface px-3 py-2 text-sm text-subtle">
		{outside === 1 ? m.tt_outside_one({ n: outside }) : m.tt_outside_many({ n: outside })}
	</p>
{/if}

<TimetableGrid {days} {blocks} {details} {today} />