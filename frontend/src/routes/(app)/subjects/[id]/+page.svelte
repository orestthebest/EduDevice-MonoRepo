<script>
    import { enhance } from '$app/forms';
	import Icon from '$lib/components/Icon.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { formatSize, formatDate, typeColor } from '$lib/format.js';

	let { data, form } = $props();

	const s = $derived(data.subject);
	const subtitle = $derived(
		`Class ${s.class_name} · ${s.teacher_name} · ${s.file_count} ${s.file_count === 1 ? 'file' : 'files'}`
	);
    	// Nur der Lehrer dieses Fachs darf hochladen
	const canEdit = $derived(data.user.role === 'lehrkraft' && s.teacher_id === data.user.id);

	// Upload-Formular
	let fileInput = $state();
	let selectedFile = $state(null);
	let title = $state('');
	let dragging = $state(false);
	let uploading = $state(false);

	// Datei ausgewählt (per Klick oder Drag & Drop): Titel automatisch aus dem Dateinamen
	function pickFile(file) {
		selectedFile = file ?? null;
		if (file && !title) title = file.name.replace(/\.[^.]+$/, '');
	}

	function onDrop(event) {
		event.preventDefault();
		dragging = false;
		const files = event.dataTransfer.files;
		if (files.length) {
			fileInput.files = files; // Datei ins echte <input> übernehmen, damit sie mitgeschickt wird
			pickFile(files[0]);
		}
	}

	function resetUpload() {
		selectedFile = null;
		title = '';
		if (fileInput) fileInput.value = '';
	}
</script>

<svelte:head>
	<title>{s.subject_name} · EduDevice</title>
</svelte:head>

<PageHeader title={s.subject_name} {subtitle} back="/subjects" />


<div class="grid items-start gap-6 {canEdit ? 'lg:grid-cols-[1fr_340px]' : ''}">
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


	{#if canEdit}
		<!-- Upload (nur Lehrer des Fachs) -->
		<section class="rounded-2xl border border-line bg-white p-6">
			<h2 class="text-lg font-semibold">Upload material</h2>

			<form
				method="POST"
				action="?/upload"
				enctype="multipart/form-data"
				class="mt-4 flex flex-col gap-4"
				use:enhance={() => {
					uploading = true;
					return async ({ result, update }) => {
						await update({ reset: false });
						uploading = false;
						if (result.type === 'success') resetUpload();
					};
				}}
			>
				{#if form?.error}
					<p class="rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">{form.error}</p>
				{/if}
				{#if form?.uploaded}
					<p class="rounded-lg border border-success/30 bg-success/12 px-4 py-3 text-sm text-success-dark">Material uploaded.</p>
				{/if}

				<!-- Drop-Zone: <label> öffnet beim Klick den Datei-Dialog -->
				<label
					class="flex cursor-pointer flex-col items-center rounded-xl border-2 border-dashed px-4 py-8 text-center transition
					{dragging ? 'border-accent bg-accent-xlight' : 'border-muted/40 bg-surface hover:border-accent/60'}"
					ondragover={(e) => { e.preventDefault(); dragging = true; }}
					ondragleave={() => (dragging = false)}
					ondrop={onDrop}
				>
					<span class="grid size-10 place-items-center rounded-xl bg-white text-accent-dark">
						<Icon name="upload" />
					</span>
					{#if selectedFile}
						<span class="mt-3 max-w-full truncate text-sm font-semibold">{selectedFile.name}</span>
						<span class="text-xs text-subtle">{formatSize(selectedFile.size)} · click to change</span>
					{:else}
						<span class="mt-3 text-sm font-semibold">Drop a file or click to choose</span>
						<span class="mt-1 text-xs text-subtle">
							{data.allowedExtensions.slice(0, 5).join(', ').toUpperCase()} … · max. {data.maxSizeMb} MB
						</span>
					{/if}
					<input
						bind:this={fileInput}
						type="file"
						name="file"
						required
						accept={data.allowedExtensions.map((e) => '.' + e).join(',')}
						class="sr-only"
						onchange={(e) => pickFile(e.currentTarget.files[0])}
					/>
				</label>

				<div>
					<label for="title" class="label">Title</label>
					<input id="title" name="title" bind:value={title} required maxlength="150"
						placeholder="e.g. Exercise sheet 7" class="input" />
				</div>

				<button type="submit" disabled={uploading || !selectedFile}
					class="inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white transition hover:bg-accent-dark disabled:cursor-not-allowed disabled:opacity-50">
					<Icon name="upload" /> {uploading ? 'Uploading…' : 'Upload'}
				</button>

				<p class="text-xs text-subtle">Every student in this subject can download it.</p>
			</form>
		</section>
	{/if}
</div>