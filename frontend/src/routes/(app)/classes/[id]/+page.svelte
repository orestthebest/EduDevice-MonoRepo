<script>
	import { enhance } from '$app/forms';
	import Icon from '$lib/components/Icon.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { SPLIT_GROUPS, ELECTIVES } from '$lib/groups.js';
	import { m } from '$lib/paraglide/messages.js';

	let { data, form } = $props();

	const c = $derived(data.schoolClass);

	let savingTeacher = $state(false);

	// ---------- Gruppe (X/Y) + Wahlfach ----------
	// data.groups = null -> die API kann das noch nicht, Spalten ausblenden
	const hasGroups = $derived(data.groups !== null);
	const assigned = $derived(new Map((data.groups ?? []).map((g) => [g.student_id, g])));
	let groupsDirty = $state(false); // ungespeicherte Änderungen?
	let savingGroups = $state(false);

	// Wie viele SchülerInnen sind in X, Y, MED, ...? (Kurzübersicht über der Liste)
	const groupCounts = $derived(
		[...SPLIT_GROUPS, ...ELECTIVES.map((e) => e.key)].map((key) => ({
			key,
			n: (data.groups ?? []).filter((g) => g.group === key || g.elective === key).length
		}))
	);

	// Suche im "Assign student"-Feld
	let search = $state('');
	const filteredStudents = $derived(
		data.assignableStudents.filter((st) =>
			`${st.first_name} ${st.last_name} ${st.username}`.toLowerCase().includes(search.toLowerCase())
		)
	);
</script>

<svelte:head>
	<title>{m.class_name({ name: c.name })} · EduDevice</title>
</svelte:head>

<PageHeader title={m.class_name({ name: c.name })} subtitle="{c.school_year} · {data.students.length === 1 ? m.cls_n_student({ n: data.students.length }) : m.cls_n_students({ n: data.students.length })}" back="/classes" />

<!-- Klassenvorstand: prüft die Entschuldigungen der Schüler dieser Klasse -->
<section class="mb-4 rounded-xl border border-line bg-white p-4 sm:p-5">
	<h2 class="text-base font-semibold">{m.cls_class_teacher()}</h2>
	<p class="text-sm text-subtle">{m.cls_teacher_hint({ name: c.name })}</p>

	<form method="POST" action="?/setClassTeacher" class="mt-3 flex flex-col gap-3 sm:flex-row sm:items-end"
		use:enhance={() => {
			savingTeacher = true;
			return async ({ update }) => {
				await update({ reset: false });
				savingTeacher = false;
			};
		}}>
		<div class="flex-1">
			<label for="class_teacher" class="label">{m.cls_teacher()}</label>
			<select id="class_teacher" name="class_teacher_id" class="input" value={c.class_teacher_id ?? ''}>
				<option value="">{m.cls_no_teacher()}</option>
				{#each data.teachers as t (t.id)}
					<option value={t.id}>{t.last_name} {t.first_name} · {t.username}</option>
				{/each}
			</select>
		</div>
		<button type="submit" class="btn-primary sm:w-auto sm:px-5" disabled={savingTeacher}>
			{savingTeacher ? m.saving() : m.save()}
		</button>
	</form>

	{#if form?.teacherError}
		<p class="mt-4 rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">{form.teacherError}</p>
	{:else if form?.teacherSaved}
		<p class="mt-4 rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-sm text-success-dark">{m.cls_teacher_saved()}</p>
	{/if}
</section>

<div class="grid items-start gap-4 lg:grid-cols-[1fr_340px]">
	<!-- Links: Schüler in der Klasse -->
	<section class="rounded-xl border border-line bg-white p-4 sm:p-5">
		<div class="mb-3 flex flex-wrap items-center justify-between gap-2">
			<h2 class="text-base font-semibold">{m.cls_students_in()}</h2>
			{#if hasGroups && data.students.length > 0}
				<p class="text-xs text-subtle">
					{#each groupCounts as g, i (g.key)}{i > 0 ? ' · ' : ''}<span class="font-semibold text-navy">{g.key}</span> {g.n}{/each}
				</p>
			{/if}
		</div>

		<!-- Gruppen-Formular: die Auswahlfelder in den Zeilen gehören über form="groups-form" dazu
		     (eigene <form> pro Zeile geht nicht, weil dort schon das Entfernen-Formular ist) -->
		<form id="groups-form" method="POST" action="?/saveGroups" class="hidden"
			use:enhance={() => {
				savingGroups = true;
				return async ({ result, update }) => {
					await update({ reset: false });
					savingGroups = false;
					if (result.type === 'success') groupsDirty = false;
				};
			}}></form>

		{#if form?.studentError}
			<p class="mb-4 rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">{form.studentError}</p>
		{/if}

		{#if data.students.length === 0}
			<p class="rounded-lg bg-surface px-3 py-6 text-center text-sm text-subtle">{m.cls_no_students()}</p>
		{:else}
			<ul class="divide-y divide-divider">
				{#each data.students as st (st.id)}
					<li class="flex items-center gap-3 py-2">
						<span class="bg-brand-gradient grid size-8 shrink-0 place-items-center rounded-full text-xs font-semibold text-white">
							{(st.first_name[0] + st.last_name[0]).toUpperCase()}
						</span>
						<div class="min-w-0 flex-1">
							<p class="truncate text-sm font-medium">{st.first_name} {st.last_name}</p>
							<p class="text-xs text-subtle">{st.username}</p>
						</div>
						{#if hasGroups}
							<!-- Gruppe X/Y und Wahlfach -->
							<select name="group_{st.id}" form="groups-form" value={assigned.get(st.id)?.group ?? ''}
								onchange={() => (groupsDirty = true)} aria-label={m.cls_group_of({ name: st.first_name })}
								class="input w-auto py-1 pr-7 text-xs">
								<option value="">{m.cls_no_group()}</option>
								{#each SPLIT_GROUPS as g (g)}<option value={g}>{m.cls_group()} {g}</option>{/each}
							</select>
							<select name="elective_{st.id}" form="groups-form" value={assigned.get(st.id)?.elective ?? ''}
								onchange={() => (groupsDirty = true)} aria-label={m.cls_elective_of({ name: st.first_name })}
								class="input w-auto py-1 pr-7 text-xs">
								<option value="">{m.cls_no_elective()}</option>
								{#each ELECTIVES as e (e.key)}<option value={e.key} title={e.label}>{e.key}</option>{/each}
							</select>
						{/if}
						<form method="POST" action="?/removeStudent" use:enhance>
							<input type="hidden" name="student_id" value={st.id} />
							<button
								type="submit"
								title={m.cls_remove_hint()}
								class="inline-flex cursor-pointer items-center gap-1 rounded-md border border-ghost px-2 py-1 text-xs font-medium text-subtle transition hover:border-error hover:text-error"
							>
								<Icon name="x" class="size-3.5" /> {m.prof_remove()}
							</button>
						</form>
					</li>
				{/each}
			</ul>

			{#if hasGroups}
				<!-- Speichern-Leiste für die Gruppen -->
				<div class="mt-3 flex flex-wrap items-center justify-end gap-3 border-t border-divider pt-3">
					{#if form?.groupError}
						<p class="mr-auto text-sm text-error">{form.groupError}</p>
					{:else if form?.groupsSaved && !groupsDirty}
						<p class="mr-auto text-sm text-success-dark">{m.cls_groups_saved()}</p>
					{/if}
					<button type="submit" form="groups-form" disabled={!groupsDirty || savingGroups} class="btn-primary w-auto px-5">
						{savingGroups ? m.saving() : m.cls_save_groups()}
					</button>
				</div>
			{/if}
		{/if}
	</section>

	<!-- Rechts: Schüler ohne Klasse zuweisen -->
	<section class="rounded-xl border border-line bg-white p-4 sm:p-5">
		<h2 class="text-base font-semibold">{m.cls_assign()}</h2>
		<p class="text-sm text-subtle">{m.cls_assign_hint({ year: c.school_year })}</p>

		<form method="POST" action="?/addStudent" class="mt-3 flex flex-col gap-3" use:enhance={() => async ({ update }) => { await update(); search = ''; }}>
			<input bind:value={search} placeholder={m.subj_search()} class="input" autocomplete="off" />

			{#if filteredStudents.length === 0}
				<p class="rounded-lg bg-surface px-3 py-4 text-center text-sm text-subtle">
					{data.assignableStudents.length === 0 ? m.cls_all_assigned() : m.subj_no_student_found()}
				</p>
			{:else}
				<!-- size="7" macht aus dem Dropdown eine Liste -->
				<select name="student_id" size="7" required class="input py-1">
					{#each filteredStudents as st (st.id)}
						<option value={st.id} class="rounded px-2 py-1.5">{st.last_name} {st.first_name} · {st.username}</option>
					{/each}
				</select>
			{/if}

			<button type="submit" disabled={filteredStudents.length === 0}
				class="inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent-dark disabled:cursor-not-allowed disabled:opacity-50">
				<Icon name="plus" /> {m.cls_assign_to({ name: c.name })}
			</button>

			<p class="text-xs text-subtle">{m.cls_assign_note()}</p>
		</form>
	</section>
</div>
