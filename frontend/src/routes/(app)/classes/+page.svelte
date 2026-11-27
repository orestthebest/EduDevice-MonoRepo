<script>
	import Icon from '$lib/components/Icon.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { m } from '$lib/paraglide/messages.js';

	let { data } = $props();
</script>

<svelte:head>
	<title>{m.nav_classes_students()} · EduDevice</title>
</svelte:head>

<PageHeader title={m.nav_classes_students()} subtitle={m.cls_subtitle()} />

{#if data.classes.length === 0}
	<div class="rounded-xl border border-dashed border-ghost bg-white px-6 py-10 text-center">
		<p class="font-semibold">{m.cls_none()}</p>
	</div>
{:else}
	<!-- Klassen als kompakte Karten (gleicher Stil wie die Fächer) -->
	<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
		{#each data.classes as c (c.id)}
			<a href="/classes/{c.id}"
				class="group flex items-center gap-3 rounded-xl border border-line bg-white p-3.5 transition hover:border-accent/50">
				<span class="grid size-10 shrink-0 place-items-center rounded-lg bg-surface text-navy transition group-hover:bg-accent-light group-hover:text-accent-dark">
					<Icon name="users" />
				</span>
				<div class="min-w-0 flex-1">
					<h2 class="truncate text-sm font-semibold">{m.class_name({ name: c.name })}</h2>
					<p class="truncate text-xs text-subtle">
						{c.class_teacher_name ? m.cls_teacher_is({ name: c.class_teacher_name }) : m.cls_no_teacher_yet()}
					</p>
				</div>
				<span class="shrink-0 self-start rounded-md bg-accent-light px-2 py-0.5 text-xs font-semibold text-accent-dark">
					{c.school_year}
				</span>
			</a>
		{/each}
	</div>
{/if}