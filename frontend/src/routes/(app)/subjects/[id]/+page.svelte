<script>
    import { enhance } from '$app/forms';
	import Icon from '$lib/components/Icon.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { formatSize, formatDate, typeColor } from '$lib/format.js';
	import { m } from '$lib/paraglide/messages.js';
	import SubjectIcon from '$lib/components/SubjectIcon.svelte';
	import { subjectTarget } from '$lib/groups.js';

	let { data, form } = $props();

	const s = $derived(data.subject);
	const subtitle = $derived(
		`${m.class_name({ name: subjectTarget(s) })} · ${s.teacher_name} · ${s.file_count} ${s.file_count === 1 ? m.subj_file() : m.subj_files()}`
	);
    	// Nur der Lehrer dieses Fachs darf hochladen
	const canEdit = $derived(data.user.role === 'lehrkraft' && s.teacher_id === data.user.id);

	// Upload-Formular
	let fileInput = $state();
	let selectedFile = $state(null);
	let title = $state('');
	let dragging = $state(false);
	let uploading = $state(false);
	let uploadingImage = $state(false); // Fachbild wird gerade hochgeladen

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
	<!-- Fachbild links vom Titel -->
	{#snippet lead()}<SubjectIcon subject={s} />{/snippet}

	{#if canEdit}
		<!-- Fachbild ändern: Datei wählen -> Formular schickt sich sofort ab (wie beim Profilbild) -->
		<form method="POST" action="?/uploadImage" enctype="multipart/form-data"
			use:enhance={() => {
				uploadingImage = true;
				return async ({ update }) => {
					await update();
					uploadingImage = false;
				};
			}}>
			<label title={m.prof_image_hint()}
				class="inline-flex h-8 cursor-pointer items-center gap-2 rounded-lg border border-line bg-white px-3 text-sm font-medium text-subtle transition hover:border-accent hover:text-accent-dark">
				<Icon name="upload" />
				<span class="hidden sm:inline">
					{uploadingImage ? m.prof_uploading() : s.image ? m.prof_change_picture() : m.prof_upload_picture()}
				</span>
				<input type="file" name="file" accept="image/jpeg,image/png,image/webp" class="hidden"
					disabled={uploadingImage} onchange={(e) => e.currentTarget.form.requestSubmit()} />
			</label>
		</form>
		{#if s.image}
			<form method="POST" action="?/removeImage" use:enhance>
				<button type="submit" title={m.prof_remove()} aria-label={m.prof_remove()}
					class="grid size-8 cursor-pointer place-items-center rounded-lg border border-line bg-white text-subtle transition hover:border-error hover:text-error">
					<Icon name="x" class="size-4" />
				</button>
			</form>
		{/if}
	{/if}
	{#if canEdit || data.user.role === 'schueler'}
		<a href="/subjects/{s.id}/quizzes"
			class="inline-flex h-8 items-center gap-2 rounded-lg bg-accent px-3 text-sm font-medium text-white transition hover:bg-accent-dark">
			<Icon name="check" /> {m.quizzes()}
		</a>
	{/if}
	{#if canEdit}
		<button
			type="button"
			onclick={() => askDelete('deleteSubject', null, m.subj_delete_title({ name: s.subject_name }), m.subj_delete_text({ className: s.class_name, count: s.file_count }))}
			class="inline-flex h-8 cursor-pointer items-center gap-2 rounded-lg border border-line bg-white px-3 text-sm font-medium text-subtle transition hover:border-error hover:text-error"
		>
			<Icon name="trash" /> {m.subj_delete()}
		</button>
	{/if}
</PageHeader>

{#if form?.imageError}
	<p class="mb-3 rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">{form.imageError}</p>
{/if}

{#if canEdit}
	<!-- Tabs: Materials | Students -->
	<div class="mb-3 inline-flex gap-0.5 rounded-lg border border-line bg-white p-0.5">
		{#each [['materials', m.materials(), data.materials.length], ['students', m.students(), data.students.length]] as [key, label, count] (key)}
			<button
				type="button"
				onclick={() => (tab = key)}
				class="inline-flex cursor-pointer items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition
				{tab === key ? 'bg-accent-light text-accent-dark' : 'text-subtle hover:bg-surface hover:text-navy'}"
			>
				{label}
				<span class="rounded-md px-1.5 text-xs {tab === key ? 'bg-white/70' : 'bg-surface'}">{count}</span>
			</button>
		{/each}
	</div>
{/if}

{#if tab === 'materials'}


<div class="grid items-start gap-4 {canEdit ? 'lg:grid-cols-[1fr_340px]' : ''}">
<!-- Materialien -->
<section class="rounded-xl border border-line bg-white p-4 sm:p-5">
	<h2 class="mb-3 text-base font-semibold">{m.materials()}</h2>

	{#if data.materials.length === 0}
		<p class="rounded-lg bg-surface px-3 py-6 text-center text-sm text-subtle">{m.dash_no_materials()}</p>
	{:else}
		<ul class="divide-y divide-divider">
			{#each data.materials as mat (mat.id)}
				<li class="flex items-center gap-3 py-2">
					<!-- Farbiges Badge mit Dateityp -->
					<span class="grid h-9 w-11 shrink-0 place-items-center rounded-md text-[11px] font-bold uppercase {typeColor(mat.ext)}">
						{mat.ext}
					</span>

					<div class="min-w-0 flex-1">
						<p class="truncate text-sm font-medium">{mat.title}</p>
						<p class="text-xs text-subtle">{m.subj_uploaded({ date: formatDate(mat.uploaded_at) })} · {formatSize(mat.size_bytes)}</p>
					</div>

					<!-- data-sveltekit-reload: normaler Browser-Download statt SvelteKit-Navigation -->
					<a
						href="/materials/{mat.id}"
						data-sveltekit-reload
						class="inline-flex items-center gap-1.5 rounded-md border border-ghost px-2.5 py-1 text-xs font-medium transition hover:border-accent hover:text-accent-dark"
					>
						<Icon name="download" class="size-3.5" /> {m.download()}
					</a>
                    {#if canEdit}
							<button
								type="button"
								onclick={() => askDelete('deleteMaterial', mat.id, m.mat_delete_title(), m.mat_delete_text({ title: mat.title }))}
								class="grid size-7 cursor-pointer place-items-center rounded-md border border-ghost text-subtle transition hover:border-error hover:text-error"
								title={m.delete()} aria-label={m.delete_item({ name: mat.title })}
							>
								<Icon name="trash" class="size-3.5" />
							</button>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}
</section>


	{#if canEdit}
		<!-- Upload (nur Lehrer des Fachs) -->
		<section class="rounded-xl border border-line bg-white p-4 sm:p-5">
			<h2 class="text-base font-semibold">{m.subj_upload_material()}</h2>

			<form
				method="POST"
				action="?/upload"
				enctype="multipart/form-data"
				class="mt-3 flex flex-col gap-3"
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
					<p class="rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">{form.error}</p>
				{/if}
				{#if form?.uploaded}
					<p class="rounded-lg border border-success/30 bg-success/12 px-3 py-2 text-sm text-success-dark">{m.subj_uploaded_ok()}</p>
				{/if}

				<!-- Drop-Zone: <label> öffnet beim Klick den Datei-Dialog -->
				<label
					class="flex cursor-pointer flex-col items-center rounded-lg border-2 border-dashed px-4 py-5 text-center transition
					{dragging ? 'border-accent bg-accent-xlight' : 'border-muted/40 bg-surface hover:border-accent/60'}"
					ondragover={(e) => { e.preventDefault(); dragging = true; }}
					ondragleave={() => (dragging = false)}
					ondrop={onDrop}
				>
					<span class="grid size-9 place-items-center rounded-lg bg-white text-accent-dark">
						<Icon name="upload" />
					</span>
					{#if selectedFile}
						<span class="mt-2 max-w-full truncate text-sm font-semibold">{selectedFile.name}</span>
						<span class="text-xs text-subtle">{formatSize(selectedFile.size)} · {m.subj_click_change()}</span>
					{:else}
						<span class="mt-2 text-sm font-semibold">{m.subj_drop()}</span>
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
					<label for="title" class="label">{m.title()}</label>
					<input id="title" name="title" bind:value={title} required maxlength="150"
						placeholder={m.subj_title_placeholder()} class="input" />
				</div>

				<button type="submit" disabled={uploading || !selectedFile}
					class="inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent-dark disabled:cursor-not-allowed disabled:opacity-50">
					<Icon name="upload" /> {uploading ? m.prof_uploading() : m.upload()}
				</button>

				<p class="text-xs text-subtle">{m.subj_upload_hint()}</p>
			</form>
		</section>
	{/if}
</div>

{:else}
	<!-- Schüler-Verwaltung (nur Lehrer des Fachs) -->
	<div class="grid items-start gap-4 lg:grid-cols-[1fr_340px]">
		<section class="rounded-xl border border-line bg-white p-4 sm:p-5">
			<h2 class="mb-3 text-base font-semibold">{m.subj_students_in()}</h2>

			{#if form?.studentError}
				<p class="mb-4 rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">{form.studentError}</p>
			{/if}

			{#if data.students.length === 0}
				<p class="rounded-lg bg-surface px-3 py-6 text-center text-sm text-subtle">{m.subj_no_students()}</p>
			{:else}
				<ul class="divide-y divide-divider">
					{#each data.students as st (st.id)}
						<li class="flex items-center gap-3 py-2">
							<span class="bg-brand-gradient grid size-8 shrink-0 place-items-center rounded-full text-xs font-semibold text-white">
								{(st.first_name[0] + st.last_name[0]).toUpperCase()}
							</span>
							<div class="min-w-0 flex-1">
								<p class="truncate text-sm font-medium">{st.first_name} {st.last_name}</p>
								<p class="text-xs text-subtle">{st.username}{st.class_name ? ` · ${st.class_name}` : ''}</p>
							</div>
							<form method="POST" action="?/removeStudent" use:enhance>
								<input type="hidden" name="student_id" value={st.id} />
								<button
									type="submit"
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

		<section class="rounded-xl border border-line bg-white p-4 sm:p-5">
			<h2 class="text-base font-semibold">{m.subj_add_student()}</h2>

			<form method="POST" action="?/addStudent" class="mt-3 flex flex-col gap-3" use:enhance={() => async ({ update }) => { await update(); search = ''; }}>
				<input bind:value={search} placeholder={m.subj_search()} class="input" autocomplete="off" />

				{#if filteredStudents.length === 0}
					<p class="rounded-lg bg-surface px-3 py-4 text-center text-sm text-subtle">
						{data.addableStudents.length === 0
						? m.subj_no_more({ className: s.class_name })
						: m.subj_no_student_found()}
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
					<Icon name="plus" /> {m.subj_add_to()}
				</button>
			</form>
		</section>
	</div>
{/if}


{#if canEdit}
	<!-- Bestätigungs-Dialog: Löschen (Material oder Fach) -->
	<dialog
		bind:this={confirmDialog}
		class="m-auto w-full max-w-sm rounded-xl border border-line bg-white p-0 text-navy shadow-xl backdrop:bg-navy/35"
	>
		<form
			method="POST"
			action="?/{confirm.action}"
			class="p-5"
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
			<span class="grid size-10 place-items-center rounded-lg bg-error/12 text-error">
				<Icon name="trash" class="size-5" />
			</span>
			<h2 class="mt-3 text-base font-bold">{confirm.title}</h2>
			<p class="mt-1 text-sm text-subtle">{confirm.text}</p>

			{#if form?.deleteError}
				<p class="mt-4 rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">{form.deleteError}</p>
			{/if}

			<input type="hidden" name="material_id" value={confirm.id ?? ''} />

			<div class="mt-4 flex justify-end gap-2">
				<button type="button" onclick={() => confirmDialog.close()}
					class="cursor-pointer rounded-lg border border-ghost px-4 py-2 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
					{m.cancel()}
				</button>
				<button type="submit" disabled={deleting}
					class="cursor-pointer rounded-lg bg-error px-4 py-2 text-sm font-medium text-white transition hover:bg-error/90 disabled:opacity-60">
					{deleting ? m.deleting() : m.delete()}
				</button>
			</div>
		</form>
	</dialog>
{/if}
