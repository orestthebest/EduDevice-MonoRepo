<script>
	import Icon from '$lib/components/Icon.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';

	let { data } = $props();
</script>

<svelte:head>
	<title>Classes & students · EduDevice</title>
</svelte:head>

<PageHeader title="Classes & students" subtitle="Assign students to their class. They are added to all subjects of that class automatically." />

{#if data.classes.length === 0}
	<div class="rounded-2xl border border-dashed border-ghost bg-white px-6 py-14 text-center">
		<p class="font-semibold">No classes yet</p>
	</div>
{:else}
	<!-- Klassen als Karten (gleicher Stil wie die Fächer) -->
	<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
		{#each data.classes as c (c.id)}
			<a
				href="/classes/{c.id}"
				class="group overflow-hidden rounded-2xl border border-line bg-white transition hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-[0_8px_24px_rgb(27_20_100/0.08)]"
			>
				<div class="bg-brand-gradient h-1.5"></div>
				<div class="p-5">
					<div class="flex items-start justify-between">
						<span class="grid size-10 place-items-center rounded-xl bg-surface text-navy transition group-hover:bg-accent-light group-hover:text-accent-dark">
							<Icon name="grid" />
						</span>
						<span class="rounded-full bg-accent-light px-2.5 py-1 text-xs font-semibold text-accent-dark">
							{c.school_year}
						</span>
					</div>
					<h2 class="mt-4 text-lg font-semibold">Class {c.name}</h2>
				</div>
			</a>
		{/each}
	</div>
{/if}