<script>
	import { enhance } from '$app/forms';
	import Icon from '$lib/components/Icon.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';

	let { data, form } = $props();

	const isStudent = $derived(data.user.role === 'schueler');
	const isTeacher = $derived(data.user.role === 'lehrkraft');

	// Titel + Untertitel je nach Rolle
	const title = $derived(isTeacher ? 'Subject management' : 'Subjects & materials');
	const subtitle = $derived(
		isTeacher ? 'Create subjects, add students and share materials'
		: isStudent ? 'All subjects you are enrolled in'
		: 'All subjects of the school'
	);
    // "New subject"-Dialog (natives <dialog>-Element)
	let dialog = $state();
	let saving = $state(false);
</script>

<svelte:head>
	<title>{title} · EduDevice</title>
</svelte:head>

<PageHeader {title} {subtitle}>
	{#if isTeacher}
		<button
			type="button"
			onclick={() => dialog.showModal()}
			class="inline-flex h-10 cursor-pointer items-center gap-2 rounded-xl bg-accent px-4 text-sm font-medium text-white transition hover:bg-accent-dark"
		>
			<Icon name="plus" /> New subject
		</button>
	{/if}
</PageHeader>

{#if data.subjects.length === 0}
	<!-- Leerer Zustand -->
	<div class="rounded-2xl border border-dashed border-ghost bg-white px-6 py-14 text-center">
		<span class="mx-auto grid size-12 place-items-center rounded-xl bg-accent-light text-accent-dark">
			<Icon name="book" class="size-5" />
		</span>
		<p class="mt-4 font-semibold">No subjects yet</p>
		<p class="mt-1 text-sm text-subtle">
			{isTeacher ? 'Create your first subject to start sharing materials.'
			: isStudent ? 'Your teachers have not added you to a subject yet.'
			: 'Teachers have not created any subjects yet.'}
		</p>
	</div>
{:else}
	<!-- Fächer als Karten -->
	<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
		{#each data.subjects as s (s.id)}
			<a
				href="/subjects/{s.id}"
				class="group overflow-hidden rounded-2xl border border-line bg-white transition hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-[0_8px_24px_rgb(27_20_100/0.08)]"
			>
				<!-- Farbstreifen im Marken-Verlauf -->
				<div class="bg-brand-gradient h-1.5"></div>

				<div class="p-5">
					<div class="flex items-start justify-between">
						<span class="grid size-10 place-items-center rounded-xl bg-surface text-navy transition group-hover:bg-accent-light group-hover:text-accent-dark">
							<Icon name="book" />
						</span>
						<span class="rounded-full bg-accent-light px-2.5 py-1 text-xs font-semibold text-accent-dark">
							Class {s.class_name}
						</span>
					</div>

					<h2 class="mt-4 text-lg font-semibold">{s.subject_name}</h2>
					<p class="text-sm text-subtle">{s.teacher_name}</p>

					<div class="mt-4 flex gap-4 border-t border-divider pt-3 text-xs text-subtle">
						<span><strong class="text-navy">{s.file_count}</strong> files</span>
						{#if !isStudent}
							<span><strong class="text-navy">{s.student_count}</strong> students</span>
						{/if}
					</div>
				</div>
			</a>
		{/each}
	</div>
{/if}


{#if isTeacher}
	<!-- Dialog: neues Fach anlegen -->
	<dialog
		bind:this={dialog}
		class="m-auto w-full max-w-md rounded-2xl border border-line bg-white p-0 text-navy shadow-xl backdrop:bg-navy/35"
	>
		<form
			method="POST"
			action="?/create"
			class="p-6"
			use:enhance={() => {
				saving = true;
				return async ({ result, update }) => {
					await update();
					saving = false;
					// Bei Erfolg Dialog schließen
					if (result.type === 'success') dialog.close();
				};
			}}
		>
			<div class="flex items-start justify-between">
				<div>
					<h2 class="text-xl font-bold">New subject</h2>
					<p class="mt-1 text-sm text-subtle">All students of the class are added automatically.</p>
				</div>
				<button type="button" onclick={() => dialog.close()} class="cursor-pointer rounded-lg p-1 text-subtle hover:bg-surface" aria-label="Close">
					<Icon name="x" class="size-5" />
				</button>
			</div>

			{#if form?.error}
				<p class="mt-4 rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">{form.error}</p>
			{/if}

			<div class="mt-5 flex flex-col gap-4">
				<div>
					<label for="class_id" class="label">Class</label>
					<select id="class_id" name="class_id" required class="input">
						<option value="" disabled selected>Choose a class</option>
						{#each data.classes as c (c.id)}
							<option value={c.id}>{c.name} · {c.school_year}</option>
						{/each}
					</select>
				</div>

				<div>
					<label for="name" class="label">Subject name</label>
					<!-- list="subject-names" zeigt vorhandene Fächer als Vorschläge -->
					<input id="name" name="name" list="subject-names" required maxlength="150"
						placeholder="e.g. Mathematics" value={form?.name ?? ''} class="input" autocomplete="off" />
					<datalist id="subject-names">
						{#each data.subjectNames as n (n)}<option value={n}></option>{/each}
					</datalist>
				</div>
			</div>

			<div class="mt-6 flex justify-end gap-2">
				<button type="button" onclick={() => dialog.close()}
					class="cursor-pointer rounded-lg border border-ghost px-4 py-2.5 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
					Cancel
				</button>
				<button type="submit" disabled={saving}
					class="cursor-pointer rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white transition hover:bg-accent-dark disabled:opacity-60">
					{saving ? 'Creating…' : 'Create subject'}
				</button>
			</div>
		</form>
	</dialog>
{/if}