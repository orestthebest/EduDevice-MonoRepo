<script>
	import Icon from '$lib/components/Icon.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';

	let { data } = $props();

	const isStudent = $derived(data.user.role === 'schueler');
	const isTeacher = $derived(data.user.role === 'lehrkraft');

	// Titel + Untertitel je nach Rolle
	const title = $derived(isTeacher ? 'Subject management' : 'Subjects & materials');
	const subtitle = $derived(
		isTeacher ? 'Create subjects, add students and share materials'
		: isStudent ? 'All subjects you are enrolled in'
		: 'All subjects of the school'
	);
</script>

<svelte:head>
	<title>{title} · EduDevice</title>
</svelte:head>

<PageHeader {title} {subtitle} />

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