<script>
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import TimetableGrid from '$lib/components/TimetableGrid.svelte';
	import { enhance } from '$app/forms';
	import { WEEKDAYS, PERIODS, toBlocks } from '$lib/timetable.js';
	import { m } from '$lib/paraglide/messages.js';

	let { data } = $props();

	// Die API liefert pro Stunde nur die class_subject_id -> Fachname + Lehrkraft aus der Fächerliste dazuholen
	const blocks = $derived(
		toBlocks(
			data.slots.map((s) => {
				const subject = data.subjects.find((x) => x.id === s.class_subject_id);
				return { ...s, subject: subject?.subject_name ?? m.tt_unknown_subject(), teacher: subject?.teacher_name };
			}),
			'weekday'
		)
	);

	// ---------- Dialog: Unterrichtseinheit anlegen / bearbeiten ----------
	let lessonDialog = $state();
	let draft = $state({ class_subject_id: '', weekday: 'Mo', period_from: 1, period_to: 1, room: '' });
	let editing = $state(null); // null = neu anlegen, sonst der angeklickte Block (alte Werte + IDs)
	let confirmDelete = $state(false);
	let saving = $state(false);
	let dialogError = $state('');

	function openDialog(values, block = null) {
		draft = values;
		editing = block;
		confirmDelete = false;
		dialogError = '';
		lessonDialog.showModal();
	}

	// Klick auf ein freies Feld: Tag + Stunde sind schon ausgefüllt
	function addLesson({ day, period }) {
		openDialog({ class_subject_id: '', weekday: day.key, period_from: period, period_to: period, room: '' });
	}

	// Klick auf einen Block: Werte übernehmen, IDs aller Stunden des Blocks merken
	function editLesson(block) {
		const values = {
			class_subject_id: block.class_subject_id,
			weekday: block.day,
			period_from: block.from,
			period_to: block.to,
			room: block.room ?? ''
		};
		openDialog({ ...values }, { ...values, ids: block.items.map((s) => s.id) });
	}

	// "Bis"-Stunde darf nie vor der "Von"-Stunde liegen
	function fixRange() {
		if (draft.period_to < draft.period_from) draft.period_to = draft.period_from;
	}

	const summary = $derived(
		`${WEEKDAYS.find((w) => w.key === draft.weekday)?.label} · ${PERIODS[draft.period_from - 1].start}–${PERIODS[draft.period_to - 1].end} · ` +
			`${draft.period_to === draft.period_from ? m.tt_n_period({ n: 1 }) : m.tt_n_periods({ n: draft.period_to - draft.period_from + 1 })}`
	);
</script>

<svelte:head>
	<title>{m.tt_manage_title()} · EduDevice</title>
</svelte:head>

<PageHeader title={m.tt_manage_title()} subtitle={m.tt_manage_subtitle()} />

{#if data.classes.length === 0}
	<section class="rounded-xl border border-line bg-white p-4 sm:p-5 text-sm text-subtle">
		{m.tt_no_classes()} <a href="/classes" class="font-medium text-accent hover:underline">{m.nav_classes_students()}</a>.
	</section>
{:else}
	<!-- Klasse auswählen -->
	<div class="mb-3 flex flex-wrap gap-2">
		{#each data.classes as c (c.id)}
			<a href="?class={c.id}"
				class="rounded-lg border px-3 py-1.5 text-sm font-medium transition
				{c.id === data.schoolClass.id ? 'border-accent bg-accent-light text-accent-dark' : 'border-line bg-white text-subtle hover:border-accent hover:text-navy'}">
				{c.name}
			</a>
		{/each}
	</div>

	{#if data.mock}
		<p class="mb-4 rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-sm">
			{m.tt_demo_manage()}
		</p>
	{/if}

	{#if data.subjects.length === 0}
		<p class="mb-4 flex items-center gap-2 rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-sm">
			{m.tt_no_subjects_before({ name: data.schoolClass.name })}
			<a href="/subjects" class="font-medium text-accent hover:underline">{m.nav_all_subjects()}</a>{m.tt_no_subjects_after()}
		</p>
	{:else}
		<p class="mb-4 flex flex-wrap items-center gap-x-2 text-sm text-subtle">
			<span class="font-semibold text-navy">{m.class_name({ name: data.schoolClass.name })}</span>
			<span>· {data.slots.length === 1 ? m.tt_per_week_one({ n: data.slots.length }) : m.tt_per_week_many({ n: data.slots.length })}</span>
			<span>· {data.subjects.length === 1 ? m.tt_n_subject({ n: data.subjects.length }) : m.tt_n_subjects({ n: data.subjects.length })}</span>
			<span class="inline-flex items-center gap-1">· <Icon name="plus" class="size-3.5" /> {m.tt_click_hint()}</span>
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

	<!-- Dialog: neue Unterrichtseinheit anlegen / bearbeiten -->
	<dialog bind:this={lessonDialog}
		class="m-auto w-full max-w-md rounded-xl border border-line bg-white p-0 text-navy shadow-xl backdrop:bg-navy/35">
		<form method="POST" action={editing ? '?/update' : '?/create'} class="p-5"
			use:enhance={() => {
				saving = true;
				return async ({ result, update }) => {
					if (result.type === 'failure') dialogError = result.data?.error ?? m.tt_err_save();
					if (result.type === 'success') lessonDialog.close();
					await update({ reset: false });
					saving = false;
				};
			}}>
			<input type="hidden" name="class_id" value={data.schoolClass.id} />

			{#if editing}<input type="hidden" name="old" value={JSON.stringify(editing)} />{/if}

			<h2 class="text-base font-bold">{editing ? m.tt_edit_lesson() : m.tt_new_lesson()} · {data.schoolClass.name}</h2>
			<p class="mt-1 text-sm text-subtle">{summary}</p>

			<div class="mt-3 space-y-3">
				<div>
					<label for="tt-subject" class="label">{m.att_subject()}</label>
					<select id="tt-subject" name="class_subject_id" required class="input" bind:value={draft.class_subject_id}>
						<option value="" disabled>{m.tt_choose_subject()}</option>
						{#each data.subjects as s (s.id)}
							<option value={s.id}>{s.subject_name} · {s.teacher_name}</option>
						{/each}
					</select>
				</div>

				<div>
					<label for="tt-weekday" class="label">{m.tt_weekday()}</label>
					<select id="tt-weekday" name="weekday" class="input" bind:value={draft.weekday}>
						{#each WEEKDAYS as w (w.key)}
							<option value={w.key}>{w.label}</option>
						{/each}
					</select>
				</div>

				<div class="grid grid-cols-2 gap-3">
					<div>
						<label for="tt-from" class="label">{m.tt_from_period()}</label>
						<select id="tt-from" name="period_from" class="input" bind:value={draft.period_from} onchange={fixRange}>
							{#each PERIODS as p (p.period)}
								<option value={p.period}>{p.period}. · {p.start}</option>
							{/each}
						</select>
					</div>
					<div>
						<label for="tt-to" class="label">{m.tt_to_period()}</label>
						<select id="tt-to" name="period_to" class="input" bind:value={draft.period_to}>
							{#each PERIODS.filter((p) => p.period >= draft.period_from) as p (p.period)}
								<option value={p.period}>{p.period}. · {p.end}</option>
							{/each}
						</select>
					</div>
				</div>

				<div>
					<label for="tt-room" class="label">{m.tt_room()} <span class="font-normal text-subtle">{m.optional()}</span></label>
					<input id="tt-room" name="room" maxlength="50" class="input" placeholder={m.tt_room_placeholder()} bind:value={draft.room} />
				</div>
			</div>

			{#if dialogError}
				<p class="mt-4 rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">{dialogError}</p>
			{/if}

			<div class="mt-4 flex items-center gap-2">
				<!-- Löschen nur beim Bearbeiten, mit zweitem Klick als Bestätigung -->
				{#if editing}
					{#if confirmDelete}
						<button type="submit" formaction="?/delete" formnovalidate disabled={saving}
							class="cursor-pointer rounded-lg bg-error px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-60">
							{m.tt_really_delete()}
						</button>
					{:else}
						<button type="button" onclick={() => (confirmDelete = true)} aria-label={m.tt_delete_lesson()}
							class="cursor-pointer rounded-lg border border-ghost p-2 text-subtle transition hover:border-error hover:text-error">
							<Icon name="trash" />
						</button>
					{/if}
				{/if}

				<button type="button" onclick={() => lessonDialog.close()}
					class="ml-auto cursor-pointer rounded-lg border border-ghost px-4 py-2 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
					{m.cancel()}
				</button>
				<button type="submit" disabled={saving}
					class="cursor-pointer rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent-dark disabled:opacity-60">
					{saving ? m.saving() : editing ? m.att_save_changes() : m.tt_add_lesson()}
				</button>
			</div>
		</form>
	</dialog>

{/if}