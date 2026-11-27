<script>
	import { enhance } from '$app/forms';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import { EXCUSE_STATUS, ABSENCE_LABEL, formatDay, formatRange, formatTime, groupByDate } from '$lib/excuses.js';
	import { periodLabel, periodOf } from '$lib/timetable.js';
	import { formatSize } from '$lib/format.js';
	import Attachments from '$lib/components/Attachments.svelte';
	import { m } from '$lib/paraglide/messages.js';

	let { data, form } = $props();

	let selected = $state([]); // ausgewählte attendance-IDs
	let sending = $state(false);

	// Anhänge (max. 3) – die Liste wird ins <input> zurückgeschrieben, dort liest das Formular sie aus
	let fileInput = $state();
	let files = $state([]);
	let uploadingId = $state(null); // Entschuldigung, zu der gerade eine Datei hochgeladen wird	

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
	<title>{m.nav_excuses()} · EduDevice</title>
</svelte:head>

<PageHeader title={m.nav_excuses()} subtitle={m.exc_subtitle()} />

<!-- Neue Entschuldigung -->
<section class="rounded-xl border border-line bg-white p-4 sm:p-5">
	<h2 class="text-base font-semibold">{m.exc_submit_title()}</h2>

	{#if days.length === 0}
		<div class="mt-3 flex items-center gap-3 rounded-lg bg-surface px-3 py-2.5 text-sm text-subtle">
			<Icon name="check" class="size-5 text-success" />
			{m.exc_none_unexcused()}
		</div>
	{:else}
		<form
			method="POST"
			action="?/submit"
			enctype="multipart/form-data"
			class="mt-3"
			use:enhance={() => {
				sending = true;

					return async ({ result, update }) => {
					await update({ reset: result.type === 'success' });
					if (result.type === 'success') {
						selected = [];
						files = [];
					}
					sending = false;
				};
			}}
		>
			<!-- Fehlstunden nach Tag -->
			<div class="space-y-3">
				{#each days as day (day.date)}
					<div class="rounded-lg border border-line">
						<div class="flex items-center justify-between rounded-t-lg border-b border-divider bg-surface/60 px-3 py-1.5">
							<p class="text-sm font-semibold">{formatDay(day.date)}</p>
							<button type="button" class="cursor-pointer text-xs font-medium text-accent hover:text-accent-darker"
								onclick={() => toggleDay(day.items)}>
								{day.items.every((a) => selected.includes(a.attendance_id)) ? m.exc_deselect_day() : m.exc_whole_day()}
							</button>
						</div>

						<ul class="divide-y divide-divider">
							{#each day.items as a (a.attendance_id)}
								<li>
									<label class="flex cursor-pointer items-center gap-3 px-3 py-2 transition hover:bg-surface">
										<input type="checkbox" name="attendance_ids" value={a.attendance_id} bind:group={selected}
											class="size-4 rounded border-input text-accent focus:ring-accent/30" />
										<!-- immer die Uhrzeit, die Stunde nur wenn sie im Raster liegt -->
										<span class="w-12 shrink-0 text-sm text-subtle tabular-nums sm:w-36">
											{formatTime(a.start_time)}{#if periodOf(a.start_time)}<span class="hidden text-muted sm:inline"> · {periodLabel(a.start_time)}</span>{/if}
										</span>
										<span class="flex-1 text-sm font-medium">{a.subject_name}</span>
										<!-- Badge nur, wenn es nicht einfach "abwesend" ist (z. B. verspätet) -->
										{#if a.status !== 'abwesend'}
											<span class="rounded-md bg-warning/15 px-2 py-px text-xs font-medium text-[#b4730f]">
												{ABSENCE_LABEL[a.status] ?? a.status}
											</span>
										{/if}
									</label>
								</li>
							{/each}
						</ul>
					</div>
				{/each}
			</div>

			<!-- Begründung -->
			<div class="mt-3">
				<label for="reason" class="label">{m.exc_reason()}</label>
				<textarea id="reason" name="reason" rows="2" required minlength="5" maxlength="1000"
					class="input resize-y" placeholder={m.exc_reason_placeholder()}
					value={form?.reason ?? ''}></textarea>
			</div>

			<!-- immer da (auch bei 3 Dateien), sonst fehlen die Dateien beim Abschicken -->
			<input id="excuse-files" bind:this={fileInput} type="file" name="files" multiple
				accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" class="sr-only"
				onchange={(e) => addFiles(e.currentTarget.files)} />

			<!-- Ausgewählte Dateien als Chips (gleicher Stil wie Attachments.svelte) -->
			{#if files.length > 0}
				<ul class="mt-3 flex flex-wrap gap-2">
					{#each files as f, i (f.name + f.size + i)}
						<li class="flex max-w-full items-center gap-1 rounded-lg border border-line bg-surface py-1 pr-1 pl-3 text-sm">
							<Icon name="file" class="size-4 shrink-0 text-subtle" />
							<span class="min-w-0 truncate font-medium">{f.name}</span>
							<span class="shrink-0 pl-1 text-xs {f.size > 5 * 1024 * 1024 ? 'font-semibold text-error' : 'text-subtle'}">
								{formatSize(f.size)}
							</span>
							<button type="button" onclick={() => removeFile(i)} aria-label={m.remove_item({ name: f.name })}
								class="cursor-pointer rounded-md p-1 text-subtle transition hover:bg-white hover:text-error">
								<Icon name="x" class="size-4" />
							</button>
						</li>
					{/each}
				</ul>
			{/if}

			<!-- Unten: Datei anhängen links, Zähler + Abschicken rechts -->
			<div class="mt-3 flex flex-col gap-3 border-t border-divider pt-3 sm:flex-row sm:items-center sm:justify-between">
				<div class="flex flex-wrap items-center gap-x-3 gap-y-1">
					{#if files.length < 3}
						<label for="excuse-files"
							class="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-ghost px-3 py-1.5 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
							<Icon name="upload" class="size-4" /> {m.exc_add_file()}
						</label>
					{/if}
					<span class="text-xs text-subtle">{m.exc_attach_hint()}</span>
				</div>
				<div class="flex items-center justify-between gap-3 sm:justify-end">
					<span class="text-sm text-subtle">
						{selected.length === 1 ? m.exc_selected_one({ n: selected.length }) : m.exc_selected_many({ n: selected.length })}
					</span>
					<button type="submit" class="btn-primary w-auto px-5" disabled={sending || selected.length === 0}>
						{sending ? m.quiz_submitting() : m.exc_submit_button()}
					</button>
				</div>
			</div>
		</form>
	{/if}

	{#if form?.error}
		<p class="mt-3 rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">{form.error}</p>
	{:else if form?.success}
		<p class="mt-3 rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-sm text-success-dark">
			{m.exc_sent()}
		</p>
		{#if form.failedFiles?.length}
			<p class="mt-2 rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-sm">
				{m.exc_failed_files({ files: form.failedFiles.join(', ') })}
			</p>
		{/if}
	{/if}
</section>

<!-- Eigene Entschuldigungen -->
<section class="mt-4 rounded-xl border border-line bg-white p-4 sm:p-5">
	<h2 class="text-base font-semibold">{m.exc_mine()}</h2>

	{#if data.excuses.length === 0}
		<p class="mt-3 text-sm text-subtle">{m.exc_none_yet()}</p>
	{:else}
		<ul class="mt-1 divide-y divide-divider">
			{#each data.excuses as e (e.id)}
				<li class="py-3">
					<!-- Datum + Stunden in einer Zeile, Status rechts -->
					<div class="flex items-start justify-between gap-2">
						<p class="min-w-0 text-sm">
							<span class="font-semibold">{formatRange(e.date_from, e.date_to)}</span>
							<span class="text-subtle">· {e.absences.length} {e.absences.length === 1 ? m.exc_lesson() : m.exc_lessons()}:
								{e.absences.map((a) => a.subject_name).join(', ')}</span>
						</p>
						<span class="shrink-0 rounded-md px-2 py-0.5 text-xs font-semibold {EXCUSE_STATUS[e.status].class}">
							{EXCUSE_STATUS[e.status].label}
						</span>
					</div>
					<p class="mt-0.5 text-sm">{e.reason}</p>
					
					
					<Attachments excuseId={e.id} attachments={e.attachments ?? []} canRemove={e.status === 'pending'} />

					{#if e.status === 'pending' && (e.attachments?.length ?? 0) < 3}
						<form method="POST" action="?/addAttachment" enctype="multipart/form-data" class="mt-2"
							use:enhance={() => {
								uploadingId = e.id;
								return async ({ update }) => {
									await update();
									uploadingId = null;
								};
							}}>
							<input type="hidden" name="excuse_id" value={e.id} />
							<label class="inline-flex cursor-pointer items-center gap-1.5 text-xs font-medium text-accent hover:text-accent-darker">
								<Icon name="plus" class="size-3.5" />
								{uploadingId === e.id ? m.prof_uploading() : m.exc_add_file()}
								<input type="file" name="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
									class="sr-only" disabled={uploadingId === e.id}
									onchange={(ev) => ev.currentTarget.form.requestSubmit()} />
							</label>
						</form>
					{/if}

					{#if form?.attachError && form?.attachId === e.id}
						<p class="mt-2 rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">{form.attachError}</p>
					{/if}

					{#if e.teacher_comment}
						<p class="mt-2 rounded-lg bg-surface px-3 py-2 text-sm">
							<span class="font-medium">{m.exc_class_teacher()}</span> {e.teacher_comment}
						</p>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}
</section>