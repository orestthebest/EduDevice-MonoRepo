<script>
	import { enhance } from '$app/forms';
	import Icon from '$lib/components/Icon.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';

	let { data, form } = $props();

	const c = $derived(data.schoolClass);

	// Suche im "Assign student"-Feld
	let search = $state('');
	const filteredStudents = $derived(
		data.assignableStudents.filter((st) =>
			`${st.first_name} ${st.last_name} ${st.username}`.toLowerCase().includes(search.toLowerCase())
		)
	);
</script>

<svelte:head>
	<title>Class {c.name} · EduDevice</title>
</svelte:head>

<PageHeader title="Class {c.name}" subtitle="{c.school_year} · {data.students.length} {data.students.length === 1 ? 'student' : 'students'}" back="/classes" />

<div class="grid items-start gap-6 lg:grid-cols-[1fr_340px]">
	<!-- Links: Schüler in der Klasse -->
	<section class="rounded-2xl border border-line bg-white p-6">
		<h2 class="mb-4 text-lg font-semibold">Students in this class</h2>

		{#if form?.studentError}
			<p class="mb-4 rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">{form.studentError}</p>
		{/if}

		{#if data.students.length === 0}
			<p class="rounded-xl bg-surface px-4 py-10 text-center text-sm text-subtle">No students yet. Assign them on the right.</p>
		{:else}
			<ul class="divide-y divide-divider">
				{#each data.students as st (st.id)}
					<li class="flex items-center gap-3 py-3">
						<span class="bg-brand-gradient grid size-9 shrink-0 place-items-center rounded-full text-xs font-semibold text-white">
							{(st.first_name[0] + st.last_name[0]).toUpperCase()}
						</span>
						<div class="min-w-0 flex-1">
							<p class="truncate font-medium">{st.first_name} {st.last_name}</p>
							<p class="text-xs text-subtle">{st.username}</p>
						</div>
						<form method="POST" action="?/removeStudent" use:enhance>
							<input type="hidden" name="student_id" value={st.id} />
							<button
								type="submit"
								title="Also removes the student from all subjects of this class"
								class="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-ghost px-3 py-1.5 text-sm font-medium text-subtle transition hover:border-error hover:text-error"
							>
								<Icon name="x" /> Remove
							</button>
						</form>
					</li>
				{/each}
			</ul>
		{/if}
	</section>

	<!-- Rechts: Schüler ohne Klasse zuweisen -->
	<section class="rounded-2xl border border-line bg-white p-6">
		<h2 class="text-lg font-semibold">Assign student</h2>
		<p class="mt-1 text-sm text-subtle">Students without a class in {c.school_year}</p>

		<form method="POST" action="?/addStudent" class="mt-4 flex flex-col gap-3" use:enhance={() => async ({ update }) => { await update(); search = ''; }}>
			<input bind:value={search} placeholder="Search name or username" class="input" autocomplete="off" />

			{#if filteredStudents.length === 0}
				<p class="rounded-xl bg-surface px-4 py-6 text-center text-sm text-subtle">
					{data.assignableStudents.length === 0 ? 'Every student already has a class.' : 'No student found.'}
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
				class="inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white transition hover:bg-accent-dark disabled:cursor-not-allowed disabled:opacity-50">
				<Icon name="plus" /> Assign to class {c.name}
			</button>

			<p class="text-xs text-subtle">The student is added to all existing subjects of this class.</p>
		</form>
	</section>
</div>