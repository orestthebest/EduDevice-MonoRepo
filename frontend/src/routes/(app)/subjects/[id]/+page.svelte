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

	// Tabs (nur für den Lehrer sichtbar): "materials" oder "students"
	let tab = $state('materials');

    // Bestätigungs-Dialog zum Löschen (für Material UND ganzes Fach)
	let confirmDialog = $state();
	let confirm = $state({ action: '', id: null, title: '', text: '' });
	let deleting = $state(false);

	function askDelete(action, id, title, text) {
		confirm = { action, id, title, text };
		confirmDialog.showModal();
	}

	// Suche im "Add student"-Feld
	let search = $state('');
	const filteredStudents = $derived(
		data.addableStudents.filter((st) =>
			`${st.first_name} ${st.last_name} ${st.username}`.toLowerCase().includes(search.toLowerCase())
		)
	);
</script>

<svelte:head>
	<title>{s.subject_name} · EduDevice</title>
</svelte:head>

<PageHeader title={s.subject_name} {subtitle} back="/subjects">
	{#if canEdit}
		<button
			type="button"
			onclick={() => askDelete('deleteSubject', null, `Delete ${s.subject_name}?`, `This deletes the subject for class ${s.class_name} including all ${s.file_count} materials. Students lose access. This cannot be undone.`)}
			class="inline-flex h-10 cursor-pointer items-center gap-2 rounded-xl border border-line bg-white px-4 text-sm font-medium text-subtle transition hover:border-error hover:text-error"
		>
			<Icon name="trash" /> Delete subject
		</button>
	{/if}
</PageHeader>


{#if canEdit}
	<!-- Tabs: Materials | Students -->
	<div class="mb-5 inline-flex gap-1 rounded-xl border border-line bg-white p-1">
		{#each [['materials', 'Materials', data.materials.length], ['students', 'Students', data.students.length]] as [key, label, count] (key)}
			<button
				type="button"
				onclick={() => (tab = key)}
				class="inline-flex cursor-pointer items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition
				{tab === key ? 'bg-accent text-white' : 'text-subtle hover:bg-surface hover:text-navy'}"
			>
				{label}
				<span class="rounded-full px-2 py-0.5 text-xs {tab === key ? 'bg-white/20' : 'bg-surface'}">{count}</span>
			</button>
		{/each}
	</div>
{/if}

{#if tab === 'materials'}


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
                    {#if canEdit}
							<button
								type="button"
								onclick={() => askDelete('deleteMaterial', m.id, 'Delete material?', `"${m.title}" will be removed for all students.`)}
								class="grid size-9 cursor-pointer place-items-center rounded-lg border border-ghost text-subtle transition hover:border-error hover:text-error"
								title="Delete" aria-label="Delete {m.title}"
							>
								<Icon name="trash" />
							</button>
					{/if}
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

{:else}
	<!-- Schüler-Verwaltung (nur Lehrer des Fachs) -->
	<div class="grid items-start gap-6 lg:grid-cols-[1fr_340px]">
		<section class="rounded-2xl border border-line bg-white p-6">
			<h2 class="mb-4 text-lg font-semibold">Students in this subject</h2>

			{#if form?.studentError}
				<p class="mb-4 rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">{form.studentError}</p>
			{/if}

			{#if data.students.length === 0}
				<p class="rounded-xl bg-surface px-4 py-10 text-center text-sm text-subtle">No students yet. Add them on the right.</p>
			{:else}
				<ul class="divide-y divide-divider">
					{#each data.students as st (st.id)}
						<li class="flex items-center gap-3 py-3">
							<span class="bg-brand-gradient grid size-9 shrink-0 place-items-center rounded-full text-xs font-semibold text-white">
								{(st.first_name[0] + st.last_name[0]).toUpperCase()}
							</span>
							<div class="min-w-0 flex-1">
								<p class="truncate font-medium">{st.first_name} {st.last_name}</p>
								<p class="text-xs text-subtle">{st.username}{st.class_name ? ` · ${st.class_name}` : ''}</p>
							</div>
							<form method="POST" action="?/removeStudent" use:enhance>
								<input type="hidden" name="student_id" value={st.id} />
								<button
									type="submit"
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

		<section class="rounded-2xl border border-line bg-white p-6">
			<h2 class="text-lg font-semibold">Add student</h2>

			<form method="POST" action="?/addStudent" class="mt-4 flex flex-col gap-3" use:enhance={() => async ({ update }) => { await update(); search = ''; }}>
				<input bind:value={search} placeholder="Search name or username" class="input" autocomplete="off" />

				{#if filteredStudents.length === 0}
					<p class="rounded-xl bg-surface px-4 py-6 text-center text-sm text-subtle">
						{data.addableStudents.length === 0 ? 'All students are already in this subject.' : 'No student found.'}
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
					<Icon name="plus" /> Add to subject
				</button>
			</form>
		</section>
	</div>
{/if}


{#if canEdit}
	<!-- Bestätigungs-Dialog: Löschen (Material oder Fach) -->
	<dialog
		bind:this={confirmDialog}
		class="m-auto w-full max-w-sm rounded-2xl border border-line bg-white p-0 text-navy shadow-xl backdrop:bg-navy/35"
	>
		<form
			method="POST"
			action="?/{confirm.action}"
			class="p-6"
			use:enhance={() => {
				deleting = true;
				return async ({ result, update }) => {
					await update();
					deleting = false;
					// Bei Erfolg (oder Weiterleitung nach Fach-Löschen) Dialog schließen
					if (result.type !== 'failure') confirmDialog?.close();
				};
			}}
		>
			<span class="grid size-11 place-items-center rounded-xl bg-error/12 text-error">
				<Icon name="trash" class="size-5" />
			</span>
			<h2 class="mt-4 text-lg font-bold">{confirm.title}</h2>
			<p class="mt-1 text-sm text-subtle">{confirm.text}</p>

			{#if form?.deleteError}
				<p class="mt-4 rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">{form.deleteError}</p>
			{/if}

			<input type="hidden" name="material_id" value={confirm.id ?? ''} />

			<div class="mt-6 flex justify-end gap-2">
				<button type="button" onclick={() => confirmDialog.close()}
					class="cursor-pointer rounded-lg border border-ghost px-4 py-2.5 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
					Cancel
				</button>
				<button type="submit" disabled={deleting}
					class="cursor-pointer rounded-lg bg-error px-4 py-2.5 text-sm font-medium text-white transition hover:bg-error/90 disabled:opacity-60">
					{deleting ? 'Deleting…' : 'Delete'}
				</button>
			</div>
		</form>
	</dialog>
{/if}