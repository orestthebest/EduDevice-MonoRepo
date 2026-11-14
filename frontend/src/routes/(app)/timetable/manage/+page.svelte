<script>
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import TimetableGrid from '$lib/components/TimetableGrid.svelte';
	import { WEEKDAYS, toBlocks } from '$lib/timetable.js';

	let { data } = $props();

	// Die API liefert pro Stunde nur die class_subject_id -> Fachname + Lehrkraft aus der Fächerliste dazuholen
	const blocks = $derived(
		toBlocks(
			data.slots.map((s) => {
				const subject = data.subjects.find((x) => x.id === s.class_subject_id);
				return { ...s, subject: subject?.subject_name ?? 'Unknown subject', teacher: subject?.teacher_name };
			}),
			'weekday'
		)
	);

	// Klick auf ein freies Feld bzw. auf einen Block – die Dialoge kommen in Schritt 5b und 5c
	function addLesson({ day, period }) {
		console.log('add', day.key, period);
	}
	function editLesson(block) {
		console.log('edit', block);
	}
</script>

<svelte:head>
	<title>Manage timetables · EduDevice</title>
</svelte:head>

<PageHeader title="Manage timetables" subtitle="Create and edit the weekly timetable of each class" />

{#if data.classes.length === 0}
	<section class="rounded-2xl border border-line bg-white p-6 text-sm text-subtle">
		There are no classes yet. Create a class first under <a href="/classes" class="font-medium text-accent hover:underline">Classes & students</a>.
	</section>
{:else}
	<!-- Klasse auswählen -->
	<div class="mb-4 flex flex-wrap gap-2">
		{#each data.classes as c (c.id)}
			<a href="?class={c.id}"
				class="rounded-xl border px-4 py-2 text-sm font-medium transition
				{c.id === data.schoolClass.id ? 'border-accent bg-accent-light text-accent-dark' : 'border-line bg-white text-subtle hover:border-accent hover:text-navy'}">
				{c.name}
			</a>
		{/each}
	</div>

	{#if data.mock}
		<p class="mb-4 rounded-lg border border-warning/40 bg-warning/10 px-4 py-2.5 text-sm">
			Demo mode – changes are only kept until the dev server restarts.
		</p>
	{/if}

	{#if data.subjects.length === 0}
		<p class="mb-4 flex items-center gap-2 rounded-lg border border-warning/40 bg-warning/10 px-4 py-2.5 text-sm">
			Class {data.schoolClass.name} has no subjects yet. Add them under
			<a href="/subjects" class="font-medium text-accent hover:underline">All subjects</a> first.
		</p>
	{:else}
		<p class="mb-4 flex flex-wrap items-center gap-x-2 text-sm text-subtle">
			<span class="font-semibold text-navy">Class {data.schoolClass.name}</span>
			<span>· {data.slots.length} {data.slots.length === 1 ? 'period' : 'periods'} per week</span>
			<span>· {data.subjects.length} {data.subjects.length === 1 ? 'subject' : 'subjects'}</span>
			<span class="inline-flex items-center gap-1">· <Icon name="plus" class="size-3.5" /> click a free period to add a lesson</span>
		</p>
	{/if}

	<TimetableGrid
		days={WEEKDAYS}
		{blocks}
		dayKey="key"
		details={['teacher', 'room']}
		editable={data.subjects.length > 0}
		onCellClick={addLesson}
		onBlockClick={editLesson}
	/>
{/if}