<script>
	import Icon from '$lib/components/Icon.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { formatSize, formatDate, typeColor } from '$lib/format.js';

	let { data } = $props();

	const s = $derived(data.subject);
	const subtitle = $derived(
		`Class ${s.class_name} · ${s.teacher_name} · ${s.file_count} ${s.file_count === 1 ? 'file' : 'files'}`
	);
</script>

<svelte:head>
	<title>{s.subject_name} · EduDevice</title>
</svelte:head>

<PageHeader title={s.subject_name} {subtitle} back="/subjects" />

<!-- Materialien -->
<section class="rounded-2xl border border-line bg-white p-6">
	<h2 class="mb-4 text-lg font-semibold">Materials</h2>

	{#if data.materials.length === 0}
		<p class="rounded-xl bg-surface px-4 py-10 text-center text-sm text-subtle">No materials uploaded yet.</p>
	{:else}
		<ul class="divide-y divide-divider">
			{#each data.materials as m (m.id)}
				<li class="flex items-center gap-4 py-3">
					<!-- Farbiges Badge mit Dateityp -->
					<span class="grid h-10 w-12 shrink-0 place-items-center rounded-lg text-[11px] font-bold uppercase {typeColor(m.ext)}">
						{m.ext}
					</span>

					<div class="min-w-0 flex-1">
						<p class="truncate font-medium">{m.title}</p>
						<p class="text-xs text-subtle">Uploaded {formatDate(m.uploaded_at)} · {formatSize(m.size_bytes)}</p>
					</div>

					<!-- data-sveltekit-reload: normaler Browser-Download statt SvelteKit-Navigation -->
					<a
						href="/materials/{m.id}"
						data-sveltekit-reload
						class="inline-flex items-center gap-2 rounded-lg border border-ghost px-3 py-1.5 text-sm font-medium transition hover:border-accent hover:text-accent-dark"
					>
						<Icon name="download" /> Download
					</a>
				</li>
			{/each}
		</ul>
	{/if}
</section>