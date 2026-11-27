<script>
	import { enhance } from '$app/forms';
	import Icon from '$lib/components/Icon.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { m } from '$lib/paraglide/messages.js';

	let { data, form } = $props();

	const c = $derived(data.schoolClass);

	let savingTeacher = $state(false);

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
		<h2 class="mb-3 text-base font-semibold">{m.cls_students_in()}</h2>

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