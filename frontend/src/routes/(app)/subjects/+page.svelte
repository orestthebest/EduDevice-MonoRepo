<script>
	import { enhance } from '$app/forms';
	import Icon from '$lib/components/Icon.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { m } from '$lib/paraglide/messages.js';
	import SubjectIcon from '$lib/components/SubjectIcon.svelte';
	import { SPLIT_GROUPS, ELECTIVES, isElective, subjectTarget } from '$lib/groups.js';

	let { data, form } = $props();

	const isStudent = $derived(data.user.role === 'schueler');
	const isTeacher = $derived(data.user.role === 'lehrkraft');

	// Titel + Untertitel je nach Rolle
	const title = $derived(isTeacher ? m.subj_management() : m.nav_subjects_materials());
	const subtitle = $derived(
		isTeacher ? m.subj_sub_teacher()
		: isStudent ? m.subj_sub_student()
		: m.subj_sub_admin()
	);
    // "New subject"-Dialog (natives <dialog>-Element)
	let dialog = $state();
	let saving = $state(false);

	// Für wen ist das neue Fach? Bei Wahlfächern können weitere Klassen (gleiches Schuljahr) dazukommen
	let newClassId = $state('');
	let newGroup = $state('');
	const newClass = $derived(data.classes.find((c) => c.id === Number(newClassId)));
	const otherClasses = $derived(
		newClass ? data.classes.filter((c) => c.id !== newClass.id && c.school_year === newClass.school_year) : []
	);
</script>

<svelte:head>
	<title>{title} · EduDevice</title>
</svelte:head>

<PageHeader {title} {subtitle}>
	{#if isTeacher}
		<button
			type="button"
			onclick={() => dialog.showModal()}
			class="inline-flex h-8 cursor-pointer items-center gap-2 rounded-lg bg-accent px-3 text-sm font-medium text-white transition hover:bg-accent-dark"
		>
			<Icon name="plus" /> {m.subj_new()}
		</button>
	{/if}
</PageHeader>

{#if data.subjects.length === 0}
	<!-- Leerer Zustand -->
	<div class="rounded-xl border border-dashed border-ghost bg-white px-6 py-10 text-center">
		<span class="mx-auto grid size-10 place-items-center rounded-lg bg-accent-light text-accent-dark">
			<Icon name="book" class="size-5" />
		</span>
		<p class="mt-3 font-semibold">{m.subj_none()}</p>
		<p class="mt-1 text-sm text-subtle">
				{isTeacher ? m.subj_none_teacher() : isStudent ? m.subj_none_student() : m.subj_none_admin()}
		</p>
	</div>
{:else}
	<!-- Fächer als kompakte Karten: Symbol, Name + Lehrkraft, Klasse rechts -->
	<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
		{#each data.subjects as s (s.id)}
			<a href="/subjects/{s.id}"
				class="group rounded-xl border border-line bg-white p-3.5 transition hover:border-accent/50">
				<div class="flex items-center gap-3">
					<SubjectIcon subject={s} />
					<div class="min-w-0 flex-1">
						<h2 class="truncate text-sm font-semibold">{s.subject_name}</h2>
						<p class="truncate text-xs text-subtle">{s.teacher_name}</p>
					</div>
					<span class="shrink-0 self-start rounded-md bg-accent-light px-2 py-0.5 text-xs font-semibold text-accent-dark">
						{subjectTarget(s)}
					</span>
				</div>

				<div class="mt-3 flex gap-4 border-t border-divider pt-2 text-xs text-subtle">
					<span><strong class="text-navy">{s.file_count}</strong> {s.file_count === 1 ? m.subj_file() : m.subj_files()}</span>
					{#if !isStudent}
						<span><strong class="text-navy">{s.student_count}</strong> {m.subj_students()}</span>
					{/if}
				</div>
			</a>
		{/each}
	</div>
{/if}


{#if isTeacher}
	<!-- Dialog: neues Fach anlegen -->
	<dialog
		bind:this={dialog}
		class="m-auto w-full max-w-md rounded-xl border border-line bg-white p-0 text-navy shadow-xl backdrop:bg-navy/35"
	>
		<form
			method="POST"
			action="?/create"
			class="p-5"
			use:enhance={() => {
				saving = true;
				return async ({ result, update }) => {
					await update();
					saving = false;
					// Bei Erfolg Dialog schließen und Auswahl zurücksetzen
					if (result.type === 'success') {
						dialog.close();
						newClassId = '';
						newGroup = '';
					}
				};
			}}
		>
			<div class="flex items-start justify-between">
				<div>
					<h2 class="text-lg font-bold">{m.subj_new()}</h2>
					<p class="text-sm text-subtle">{m.subj_new_hint()}</p>
				</div>
				<button type="button" onclick={() => dialog.close()} class="cursor-pointer rounded-lg p-1 text-subtle hover:bg-surface" aria-label={m.close()}>
					<Icon name="x" class="size-5" />
				</button>
			</div>

			{#if form?.error}
				<p class="mt-4 rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">{form.error}</p>
			{/if}

			<div class="mt-4 flex flex-col gap-3">
				<div>
					<label for="class_id" class="label">{m.class_label()}</label>
					<select id="class_id" name="class_id" required class="input" bind:value={newClassId}>
						<option value="" disabled>{m.subj_choose_class()}</option>
						{#each data.classes as c (c.id)}
							<option value={c.id}>{c.name} · {c.school_year}</option>
						{/each}
					</select>
				</div>

				<!-- Für wen: ganze Klasse, Gruppe X/Y oder Wahlfach -->
				<div>
					<label for="group" class="label">{m.subj_for()}</label>
					<select id="group" name="group" class="input" bind:value={newGroup}>
						<option value="">{m.subj_whole_class()}</option>
						<optgroup label={m.subj_groups()}>
							{#each SPLIT_GROUPS as g (g)}<option value={g}>{m.cls_group()} {g}</option>{/each}
						</optgroup>
						<optgroup label={m.subj_electives()}>
							{#each ELECTIVES as e (e.key)}<option value={e.key}>{e.key} · {e.label}</option>{/each}
						</optgroup>
					</select>
				</div>

				<!-- Wahlfach: weitere Klassen, deren SchülerInnen mit diesem Wahlfach mitmachen -->
				{#if isElective(newGroup) && otherClasses.length > 0}
					<fieldset>
						<legend class="label">{m.subj_also_classes()}</legend>
						<div class="flex flex-wrap gap-2">
							{#each otherClasses as c (c.id)}
								<label class="flex cursor-pointer items-center gap-2 rounded-lg border border-line px-3 py-1.5 text-sm transition has-checked:border-accent has-checked:bg-accent-light">
									<input type="checkbox" name="class_ids" value={c.id} class="size-4 rounded border-input text-accent" />
									{c.name}
								</label>
							{/each}
						</div>
						<p class="mt-1 text-xs text-subtle">{m.subj_also_hint()}</p>
					</fieldset>
				{/if}

				<div>
					<label for="name" class="label">{m.subj_name()}</label>
					<!-- list="subject-names" zeigt vorhandene Fächer als Vorschläge -->
					<input id="name" name="name" list="subject-names" required maxlength="150"
						placeholder={m.subj_name_placeholder()} value={form?.name ?? ''} class="input" autocomplete="off" />
					<datalist id="subject-names">
						{#each data.subjectNames as n (n)}<option value={n}></option>{/each}
					</datalist>
				</div>
			</div>

			<div class="mt-4 flex justify-end gap-2">
				<button type="button" onclick={() => dialog.close()}
					class="cursor-pointer rounded-lg border border-ghost px-4 py-2 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
					{m.cancel()}
				</button>
				<button type="submit" disabled={saving}
					class="cursor-pointer rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent-dark disabled:opacity-60">
					{saving ? m.subj_creating() : m.subj_create()}
				</button>
			</div>
		</form>
	</dialog>
{/if}
