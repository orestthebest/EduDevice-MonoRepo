<script>
	import { enhance } from '$app/forms';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import { EXCUSE_STATUS, ABSENCE_LABEL, formatDay, formatTime, formatRange, groupByDate } from '$lib/excuses.js';
	import { formatSize } from '$lib/format.js';

	let { data, form } = $props();

	let selected = $state([]); // ausgewählte attendance-IDs
	let sending = $state(false);

	// Anhänge (max. 3) – die Liste wird ins <input> zurückgeschrieben, dort liest das Formular sie aus
	let fileInput = $state();
	let files = $state([]);

	function syncInput() {
		const dt = new DataTransfer();
		files.forEach((f) => dt.items.add(f));
		fileInput.files = dt.files;
	}
	function addFiles(list) {
		files = [...files, ...list].slice(0, 3);
		syncInput();
	}
	function removeFile(i) {
		files = files.filter((_, j) => j !== i);
		syncInput();
	}

	const days = $derived(groupByDate(data.absences));

	// "Whole day": alle Stunden eines Tages an- bzw. abwählen
	function toggleDay(items) {
		const ids = items.map((a) => a.attendance_id);
		const all = ids.every((id) => selected.includes(id));
		selected = all ? selected.filter((id) => !ids.includes(id)) : [...new Set([...selected, ...ids])];
	}
</script>

<svelte:head>
	<title>Excuses · EduDevice</title>
</svelte:head>

<PageHeader title="Excuses" subtitle="Excuse your absences – your class teacher reviews them" />

<!-- Neue Entschuldigung -->
<section class="rounded-2xl border border-line bg-white p-6">
	<h2 class="text-lg font-semibold">Submit an excuse</h2>
	<p class="text-sm text-subtle">Select the lessons you missed and give a reason.</p>

	{#if days.length === 0}
		<div class="mt-5 flex items-center gap-3 rounded-xl bg-surface px-4 py-4 text-sm text-subtle">
			<Icon name="check" class="size-5 text-success" />
			You have no unexcused absences.
		</div>
	{:else}
		<form
			method="POST"
			action="?/submit"
			enctype="multipart/form-data"
			class="mt-5"
			use:enhance={() => {
				sending = true;
				return async ({ result, update }) => {
					if (result.type === 'success') {
						selected = [];
						files = [];
					}
					sending = false;
				};
			}}
		>
			<!-- Fehlstunden nach Tag -->
			<div class="space-y-4">
				{#each days as day (day.date)}
					<div class="rounded-xl border border-line">
						<div class="flex items-center justify-between border-b border-divider px-4 py-2.5">
							<p class="text-sm font-semibold">{formatDay(day.date)}</p>
							<button type="button" class="cursor-pointer text-xs font-medium text-accent hover:text-accent-darker"
								onclick={() => toggleDay(day.items)}>
								{day.items.every((a) => selected.includes(a.attendance_id)) ? 'Deselect day' : 'Whole day'}
							</button>
						</div>

						<ul class="divide-y divide-divider">
							{#each day.items as a (a.attendance_id)}
								<li>
									<label class="flex cursor-pointer items-center gap-3 px-4 py-3 transition hover:bg-surface">
										<input type="checkbox" name="attendance_ids" value={a.attendance_id} bind:group={selected}
											class="size-4 rounded border-input text-accent focus:ring-accent/30" />
										<span class="w-12 text-sm text-subtle tabular-nums">{formatTime(a.start_time)}</span>
										<span class="flex-1 text-sm font-medium">{a.subject_name}</span>
										<span class="rounded-full bg-surface px-2.5 py-0.5 text-xs font-medium text-subtle">
											{ABSENCE_LABEL[a.status] ?? a.status}
										</span>
									</label>
								</li>
							{/each}
						</ul>
					</div>
				{/each}
			</div>

			<!-- Begründung -->
			<div class="mt-5">
				<label for="reason" class="label">Reason</label>
				<textarea id="reason" name="reason" rows="3" required minlength="5" maxlength="1000"
					class="input resize-y" placeholder="e.g. I was sick with a fever"
					value={form?.reason ?? ''}></textarea>
			</div>

			<div class="mt-5">
				<p class="label">Attachments <span class="font-normal text-subtle">(optional)</span></p>
				<p class="text-xs text-subtle">e.g. a doctor's note · PDF, JPG or PNG · max. 5 MB each · up to 3 files</p>

				<!-- immer da (auch bei 3 Dateien), sonst fehlen die Dateien beim Abschicken -->
				<input id="excuse-files" bind:this={fileInput} type="file" name="files" multiple
					accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" class="sr-only"
					onchange={(e) => addFiles(e.currentTarget.files)} />

				{#if files.length > 0}
					<ul class="mt-3 space-y-2">
						{#each files as f, i (f.name + f.size + i)}
							<li class="flex items-center gap-3 rounded-xl border border-line px-4 py-2.5">
								<Icon name="file" class="size-4 text-subtle" />
								<span class="min-w-0 flex-1 truncate text-sm font-medium">{f.name}</span>
								<span class="text-xs {f.size > 5 * 1024 * 1024 ? 'font-semibold text-error' : 'text-subtle'}">
									{formatSize(f.size)}
								</span>
								<button type="button" onclick={() => removeFile(i)} aria-label="Remove {f.name}"
									class="cursor-pointer rounded-lg p-1 text-subtle transition hover:bg-surface hover:text-error">
									<Icon name="x" class="size-4" />
								</button>
							</li>
						{/each}
					</ul>
				{/if}

				{#if files.length < 3}
					<label for="excuse-files"
						class="mt-3 inline-flex cursor-pointer items-center gap-2 rounded-lg border border-ghost px-4 py-2.5 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
						<Icon name="upload" /> Add file
					</label>
				{/if}
			</div>

			<div class="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
				<p class="text-sm text-subtle">
					{selected.length} {selected.length === 1 ? 'lesson' : 'lessons'} selected
				</p>
				<button type="submit" class="btn-primary sm:w-auto sm:px-6" disabled={sending || selected.length === 0}>
					{sending ? 'Submitting…' : 'Submit excuse'}
				</button>
			</div>
		</form>
	{/if}

	{#if form?.error}
		<p class="mt-4 rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">{form.error}</p>
	{:else if form?.success}
		<p class="mt-4 rounded-lg border border-success/30 bg-success/10 px-4 py-3 text-sm text-success-dark">
			Your excuse has been sent to your class teacher.
		</p>
		{#if form.failedFiles?.length}
			<p class="mt-2 rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm">
				These files could not be uploaded: {form.failedFiles.join(', ')}. You can add them under "My excuses".
			</p>
		{/if}
	{/if}
</section>

<!-- Eigene Entschuldigungen -->
<section class="mt-6 rounded-2xl border border-line bg-white p-6">
	<h2 class="text-lg font-semibold">My excuses</h2>

	{#if data.excuses.length === 0}
		<p class="mt-3 text-sm text-subtle">You haven't submitted any excuses yet.</p>
	{:else}
		<ul class="mt-4 divide-y divide-divider">
			{#each data.excuses as e (e.id)}
				<li class="py-4">
					<div class="flex flex-wrap items-center justify-between gap-2">
						<p class="font-semibold">{formatRange(e.date_from, e.date_to)}</p>
						<span class="rounded-full px-3 py-1 text-xs font-semibold {EXCUSE_STATUS[e.status].class}">
							{EXCUSE_STATUS[e.status].label}
						</span>
					</div>
					<p class="mt-1 text-xs text-subtle">
						{e.absences.length} {e.absences.length === 1 ? 'lesson' : 'lessons'}:
						{e.absences.map((a) => a.subject_name).join(', ')}
					</p>
					<p class="mt-2 text-sm">{e.reason}</p>

					{#if e.teacher_comment}
						<p class="mt-2 rounded-lg bg-surface px-3 py-2 text-sm">
							<span class="font-medium">Class teacher:</span> {e.teacher_comment}
						</p>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}
</section>