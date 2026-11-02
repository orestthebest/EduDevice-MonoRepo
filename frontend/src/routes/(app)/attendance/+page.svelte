<script>
	import { enhance } from '$app/forms';
	import { goto } from '$app/navigation';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import { formatDay, formatTime } from '$lib/excuses.js';

	let { data, form } = $props();

	let saving = $state(false);

	// Heute (lokal) -> keine Zukunftsdaten im Datumsfeld
	const now = new Date();
	const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;

	// Status pro Schüler (student_id -> 'anwesend' | 'abwesend').
	// Noch nicht erfasst = standardmäßig anwesend. Wird neu gesetzt, sobald andere Daten geladen werden.
	let statuses = $state({});
	$effect.pre(() => {
		const next = {};
		for (const s of data.lesson?.students ?? []) next[s.student_id] = s.status ?? 'anwesend';
		statuses = next;
	});

	const students = $derived(data.lesson?.students ?? []);
	const absentCount = $derived(Object.values(statuses).filter((s) => s !== 'anwesend').length);
	const recorded = $derived(students.some((s) => s.status !== null));
	const currentSubject = $derived(data.subjects.find((s) => s.id === data.subjectId));

	// Auswahl ändern = neue URL laden (Fach/Datum geändert -> Stunde neu wählen)
	function pick(changes) {
		const params = new URLSearchParams({
			subject: String(data.subjectId ?? ''),
			date: data.date,
			time: data.time,
			...changes
		});
		goto(`?${params}`, { keepFocus: true, noScroll: true });
	}

	function markAll(status) {
		for (const id of Object.keys(statuses)) statuses[id] = status;
	}
</script>

<svelte:head>
	<title>Attendance · EduDevice</title>
</svelte:head>

<PageHeader title="Attendance" subtitle="Record who was present in each lesson" />

{#if data.subjects.length === 0}
	<div class="rounded-2xl border border-dashed border-ghost bg-white px-6 py-14 text-center">
		<span class="mx-auto grid size-12 place-items-center rounded-xl bg-accent-light text-accent-dark">
			<Icon name="calendar" class="size-5" />
		</span>
		<p class="mt-4 font-semibold">No subjects yet</p>
		<p class="mt-1 text-sm text-subtle">You can take attendance once you teach a subject.</p>
	</div>
{:else}
	<div class="grid gap-6 lg:grid-cols-[1fr_320px]">
		<div class="space-y-6">
			<!-- Auswahl: Fach, Datum, Stunde -->
			<section class="grid gap-4 rounded-2xl border border-line bg-white p-6 sm:grid-cols-3">
				<div>
					<label for="subject" class="label">Subject</label>
					<select id="subject" class="input" value={data.subjectId}
						onchange={(e) => pick({ subject: e.currentTarget.value, time: '' })}>
						{#each data.subjects as s (s.id)}
							<option value={s.id}>{s.subject_name} · {s.class_name}</option>
						{/each}
					</select>
				</div>
				<div>
					<label for="date" class="label">Date</label>
					<input id="date" type="date" class="input" value={data.date} max={todayStr}
						onchange={(e) => e.currentTarget.value && pick({ date: e.currentTarget.value, time: '' })} />
				</div>
				<div>
					<label for="time" class="label">Lesson</label>
					<select id="time" class="input" value={data.time} disabled={data.slots.length === 0}
						onchange={(e) => pick({ time: e.currentTarget.value })}>
						{#each data.slots as slot (slot.timetable_id)}
							<option value={formatTime(slot.start_time)}>
								{formatTime(slot.start_time)}–{formatTime(slot.end_time)}{slot.room ? ` · ${slot.room}` : ''}
							</option>
						{:else}
							<option value="">No lesson</option>
						{/each}
					</select>
				</div>
			</section>

			<!-- Schülerliste -->
			{#if data.slotError}
				<section class="flex items-center gap-3 rounded-2xl border border-line bg-white p-6 text-sm text-subtle">
					<Icon name="calendar" class="size-5" />
					{data.slotError}
				</section>
			{:else if !data.lesson}
				<section class="flex items-center gap-3 rounded-2xl border border-line bg-white p-6 text-sm text-subtle">
					<Icon name="calendar" class="size-5" />
					{currentSubject?.subject_name} has no lesson on {formatDay(data.date)} according to the timetable.
				</section>
			{:else}
				<section class="rounded-2xl border border-line bg-white p-6">
					<div class="mb-4 flex flex-wrap items-start justify-between gap-3">
						<div>
							<h2 class="text-lg font-semibold">
								{currentSubject?.subject_name} · {currentSubject?.class_name}
							</h2>
							<p class="text-sm text-subtle">
								{formatDay(data.date)} · {formatTime(data.lesson.start_time)}–{formatTime(data.lesson.end_time)}
								{data.lesson.room ? `· ${data.lesson.room}` : ''}
							</p>
						</div>
						<span class="rounded-full px-3 py-1 text-xs font-semibold
							{recorded ? 'bg-success/12 text-success-dark' : 'bg-warning/15 text-[#b4730f]'}">
							{recorded ? 'Recorded' : 'Not recorded yet'}
						</span>
					</div>

					{#if data.lesson.cancelled}
						<p class="mb-4 rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-[#b4730f]">
							This lesson is marked as cancelled.
						</p>
					{/if}

					{#if students.length === 0}
						<p class="rounded-xl bg-surface px-4 py-6 text-center text-sm text-subtle">
							There are no students in this subject.
						</p>
					{:else}
						<form method="POST" action="?/save"
							use:enhance={() => {
								saving = true;
								return async ({ update }) => {
									await update({ reset: false });
									saving = false;
								};
							}}>
							<input type="hidden" name="class_subject_id" value={data.subjectId} />
							<input type="hidden" name="date" value={data.date} />
							<input type="hidden" name="start_time" value={data.time} />

							<div class="mb-3 flex flex-wrap items-center justify-between gap-2 text-sm">
								<p class="text-subtle">
									<span class="font-semibold text-navy">{students.length - absentCount}</span> present ·
									<span class="font-semibold {absentCount > 0 ? 'text-error' : 'text-navy'}">{absentCount}</span> absent
								</p>
								<button type="button" onclick={() => markAll('anwesend')}
									class="cursor-pointer rounded-lg border border-ghost px-3 py-1.5 font-medium transition hover:border-accent hover:text-accent-dark">
									Mark all present
								</button>
							</div>

							<ul class="divide-y divide-divider rounded-xl border border-line">
								{#each students as s (s.student_id)}
									{@const status = statuses[s.student_id]}
									<li class="flex items-center gap-3 px-4 py-2.5">
										<input type="hidden" name="student_id" value={s.student_id} />
										<input type="hidden" name="status-{s.student_id}" value={status} />

										<div class="min-w-0 flex-1">
											<p class="truncate text-sm font-medium">{s.last_name} {s.first_name}</p>
											{#if !s.enrolled}
												<p class="text-xs text-subtle">No longer in this subject</p>
											{:else if status === 'verspaetet'}
												<p class="text-xs text-subtle">Recorded as late</p>
											{/if}
										</div>

										<div class="inline-flex shrink-0 rounded-lg border border-line p-0.5 text-sm">
											<button type="button" onclick={() => (statuses[s.student_id] = 'anwesend')}
												class="cursor-pointer rounded-md px-3 py-1.5 font-medium transition
												{status === 'anwesend' ? 'bg-success/12 text-success-dark' : 'text-subtle hover:text-navy'}">
												Present
											</button>
											<button type="button" onclick={() => (statuses[s.student_id] = 'abwesend')}
												class="cursor-pointer rounded-md px-3 py-1.5 font-medium transition
												{status === 'abwesend' ? 'bg-error/12 text-error' : 'text-subtle hover:text-navy'}">
												Absent
											</button>
										</div>
									</li>
								{/each}
							</ul>

							{#if form?.error}
								<p class="mt-4 rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">{form.error}</p>
							{:else if form?.success}
								<p class="mt-4 rounded-lg border border-success/30 bg-success/10 px-4 py-3 text-sm text-success-dark">{form.success}</p>
							{/if}

							<div class="mt-5 flex justify-end">
								<button type="submit" disabled={saving} class="btn-primary text-sm sm:w-auto sm:px-6">
									{saving ? 'Saving…' : recorded ? 'Save changes' : 'Save attendance'}
								</button>
							</div>
						</form>
					{/if}
				</section>
			{/if}
		</div>

		<!-- Verlauf: bereits erfasste Stunden dieses Fachs -->
		<aside class="h-fit rounded-2xl border border-line bg-white p-6">
			<h2 class="mb-4 text-lg font-semibold">History</h2>
			{#if data.history.length === 0}
				<p class="text-sm text-subtle">No attendance recorded for this subject yet.</p>
			{:else}
				<ul class="space-y-1">
					{#each data.history as h (h.lesson_id)}
						{@const active = h.date === data.date && formatTime(h.start_time) === data.time}
						{@const absent = h.absent_count + h.late_count}
						<li>
							<a href="?subject={data.subjectId}&date={h.date}&time={formatTime(h.start_time)}"
								class="flex items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm transition
								{active ? 'bg-accent-light text-accent-dark' : 'hover:bg-surface'}">
								<span>
									<span class="font-medium">{formatDay(h.date)}</span>
									<span class="text-subtle tabular-nums">· {formatTime(h.start_time)}</span>
								</span>
								<span class="rounded-full px-2.5 py-0.5 text-xs font-semibold
									{absent > 0 ? 'bg-error/12 text-error' : 'bg-success/12 text-success-dark'}">
									{absent > 0 ? `${absent} absent` : 'All present'}
								</span>
							</a>
						</li>
					{/each}
				</ul>
			{/if}
		</aside>
	</div>
{/if}