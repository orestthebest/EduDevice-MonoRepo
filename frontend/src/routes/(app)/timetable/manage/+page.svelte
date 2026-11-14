<script>
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import TimetableGrid from '$lib/components/TimetableGrid.svelte';
	import { enhance } from '$app/forms';
	import { WEEKDAYS, PERIODS, toBlocks } from '$lib/timetable.js';

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

	// ---------- Dialog: neue Unterrichtseinheit ----------
	let addDialog = $state();
	let draft = $state({ class_subject_id: '', weekday: 'Mo', period_from: 1, period_to: 1, room: '' });
	let saving = $state(false);
	let dialogError = $state('');

	// Klick auf ein freies Feld: Tag + Stunde sind schon ausgefüllt
	function addLesson({ day, period }) {
		draft = { class_subject_id: '', weekday: day.key, period_from: period, period_to: period, room: '' };
		dialogError = '';
		addDialog.showModal();
	}

	// "Bis"-Stunde darf nie vor der "Von"-Stunde liegen
	function fixRange() {
		if (draft.period_to < draft.period_from) draft.period_to = draft.period_from;
	}

	const summary = $derived(
		`${WEEKDAYS.find((w) => w.key === draft.weekday)?.label} · ${PERIODS[draft.period_from - 1].start}–${PERIODS[draft.period_to - 1].end} · ` +
			`${draft.period_to - draft.period_from + 1} ${draft.period_to === draft.period_from ? 'period' : 'periods'}`
	);

	// Klick auf einen Block – Bearbeiten/Löschen kommt in Schritt 5c
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

	<!-- Dialog: neue Unterrichtseinheit -->
	<dialog bind:this={addDialog}
		class="m-auto w-full max-w-md rounded-2xl border border-line bg-white p-0 text-navy shadow-xl backdrop:bg-navy/35">
		<form method="POST" action="?/create" class="p-6"
			use:enhance={() => {
				saving = true;
				return async ({ result, update }) => {
					if (result.type === 'failure') dialogError = result.data?.error ?? 'Could not save the lesson';
					if (result.type === 'success') addDialog.close();
					await update({ reset: false });
					saving = false;
				};
			}}>
			<input type="hidden" name="class_id" value={data.schoolClass.id} />

			<h2 class="text-lg font-bold">New lesson · {data.schoolClass.name}</h2>
			<p class="mt-1 text-sm text-subtle">{summary}</p>

			<div class="mt-5 space-y-4">
				<div>
					<label for="tt-subject" class="label">Subject</label>
					<select id="tt-subject" name="class_subject_id" required class="input" bind:value={draft.class_subject_id}>
						<option value="" disabled>Choose a subject</option>
						{#each data.subjects as s (s.id)}
							<option value={s.id}>{s.subject_name} · {s.teacher_name}</option>
						{/each}
					</select>
				</div>

				<div>
					<label for="tt-weekday" class="label">Weekday</label>
					<select id="tt-weekday" name="weekday" class="input" bind:value={draft.weekday}>
						{#each WEEKDAYS as w (w.key)}
							<option value={w.key}>{w.label}</option>
						{/each}
					</select>
				</div>

				<div class="grid grid-cols-2 gap-3">
					<div>
						<label for="tt-from" class="label">From period</label>
						<select id="tt-from" name="period_from" class="input" bind:value={draft.period_from} onchange={fixRange}>
							{#each PERIODS as p (p.period)}
								<option value={p.period}>{p.period}. · {p.start}</option>
							{/each}
						</select>
					</div>
					<div>
						<label for="tt-to" class="label">To period</label>
						<select id="tt-to" name="period_to" class="input" bind:value={draft.period_to}>
							{#each PERIODS.filter((p) => p.period >= draft.period_from) as p (p.period)}
								<option value={p.period}>{p.period}. · {p.end}</option>
							{/each}
						</select>
					</div>
				</div>

				<div>
					<label for="tt-room" class="label">Room <span class="font-normal text-subtle">(optional)</span></label>
					<input id="tt-room" name="room" maxlength="50" class="input" placeholder="e.g. K22" bind:value={draft.room} />
				</div>
			</div>

			{#if dialogError}
				<p class="mt-4 rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">{dialogError}</p>
			{/if}

			<div class="mt-6 flex justify-end gap-2">
				<button type="button" onclick={() => addDialog.close()}
					class="cursor-pointer rounded-lg border border-ghost px-4 py-2.5 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
					Cancel
				</button>
				<button type="submit" disabled={saving}
					class="cursor-pointer rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white transition hover:bg-accent-dark disabled:opacity-60">
					{saving ? 'Saving…' : 'Add lesson'}
				</button>
			</div>
		</form>
	</dialog>

{/if}