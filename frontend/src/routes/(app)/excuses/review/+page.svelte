<script>
	import { enhance } from '$app/forms';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import { EXCUSE_STATUS, ABSENCE_LABEL, formatDay, formatTime, formatRange } from '$lib/excuses.js';
	import { formatDate } from '$lib/format.js';

	let { data, form } = $props();

	let tab = $state('pending'); // 'pending' | 'reviewed'
	let busyId = $state(null); // Entschuldigung, die gerade gespeichert wird
</script>

<svelte:head>
	<title>Excuse review · EduDevice</title>
</svelte:head>

<PageHeader title="Excuse review" subtitle="Excuses from students of your class" />

<!-- Tabs -->
<div class="mb-4 inline-flex rounded-xl border border-line bg-white p-1">
	{#each [['pending', `Pending (${data.pending.length})`], ['reviewed', 'History']] as [key, label] (key)}
		<button
			type="button"
			class="cursor-pointer rounded-lg px-4 py-2 text-sm font-medium transition
			{tab === key ? 'bg-accent-light text-accent-dark' : 'text-subtle hover:text-navy'}"
			onclick={() => (tab = key)}
		>
			{label}
		</button>
	{/each}
</div>

{#if form?.success}
	<p class="mb-4 rounded-lg border border-success/30 bg-success/10 px-4 py-3 text-sm text-success-dark">{form.success}</p>
{/if}

{#if tab === 'pending'}
	{#if data.pending.length === 0}
		<section class="flex items-center gap-3 rounded-2xl border border-line bg-white p-6 text-sm text-subtle">
			<Icon name="check" class="size-5 text-success" />
			No excuses waiting for review.
		</section>
	{:else}
		<div class="space-y-4">
			{#each data.pending as e (e.id)}
				<section class="rounded-2xl border border-line bg-white p-6">
					<!-- Kopf: Schüler, Klasse, Zeitraum -->
					<div class="flex flex-wrap items-start justify-between gap-2">
						<div>
							<h2 class="text-lg font-semibold">{e.student_name}</h2>
							<p class="text-sm text-subtle">
								Class {e.class_name} · {formatRange(e.date_from, e.date_to)} · submitted {formatDate(e.submitted_at)}
							</p>
						</div>
						<span class="rounded-full px-3 py-1 text-xs font-semibold {EXCUSE_STATUS.pending.class}">
							{EXCUSE_STATUS.pending.label}
						</span>
					</div>

					<!-- Betroffene Stunden -->
					<ul class="mt-4 divide-y divide-divider rounded-xl border border-line">
						{#each e.absences as a (a.attendance_id)}
							<li class="flex items-center gap-3 px-4 py-2.5 text-sm">
								<span class="w-28 text-subtle">{formatDay(a.date)}</span>
								<span class="w-12 text-subtle tabular-nums">{formatTime(a.start_time)}</span>
								<span class="flex-1 font-medium">{a.subject_name}</span>
								<span class="rounded-full bg-surface px-2.5 py-0.5 text-xs font-medium text-subtle">
									{ABSENCE_LABEL[a.status] ?? a.status}
								</span>
							</li>
						{/each}
					</ul>

					<!-- Begründung des Schülers -->
					<p class="mt-4 text-xs font-semibold tracking-wider text-subtle uppercase">Reason</p>
					<p class="mt-1 text-sm">{e.reason}</p>

					<!-- Entscheidung -->
					<form
						method="POST"
						action="?/review"
						class="mt-5"
						use:enhance={() => {
							busyId = e.id;
							return async ({ update }) => {
								await update();
								busyId = null;
							};
						}}
					>
						<input type="hidden" name="id" value={e.id} />
						<label for="comment-{e.id}" class="label">Comment <span class="font-normal text-subtle">(required when rejecting)</span></label>
						<textarea id="comment-{e.id}" name="comment" rows="2" maxlength="500" class="input resize-y"
							placeholder="e.g. Please bring a doctor's note"
							value={form?.id === e.id ? (form.comment ?? '') : ''}></textarea>

						{#if form?.error && form?.id === e.id}
							<p class="mt-3 rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">{form.error}</p>
						{/if}

						<div class="mt-4 flex flex-col gap-2 sm:flex-row sm:justify-end">
							<button type="submit" name="status" value="rejected" disabled={busyId === e.id}
								class="cursor-pointer rounded-lg border border-ghost px-5 py-2.5 text-sm font-medium transition hover:border-error hover:text-error">
								Reject
							</button>
							<button type="submit" name="status" value="accepted" disabled={busyId === e.id}
								class="btn-primary text-sm sm:w-auto sm:px-6">
								{busyId === e.id ? 'Saving…' : 'Accept'}
							</button>
						</div>
					</form>
				</section>
			{/each}
		</div>
	{/if}
{:else}
	<!-- Bereits entschiedene Entschuldigungen -->
	<section class="rounded-2xl border border-line bg-white p-6">
		{#if data.reviewed.length === 0}
			<p class="text-sm text-subtle">No reviewed excuses yet.</p>
		{:else}
			<ul class="divide-y divide-divider">
				{#each data.reviewed as e (e.id)}
					<li class="py-4 first:pt-0 last:pb-0">
						<div class="flex flex-wrap items-center justify-between gap-2">
							<p class="font-semibold">
								{e.student_name}
								<span class="font-normal text-subtle">· {e.class_name}</span>
							</p>
							<span class="rounded-full px-3 py-1 text-xs font-semibold {EXCUSE_STATUS[e.status].class}">
								{EXCUSE_STATUS[e.status].label}
							</span>
						</div>
						<p class="mt-1 text-xs text-subtle">
							{formatRange(e.date_from, e.date_to)} · {e.absences.length}
							{e.absences.length === 1 ? 'lesson' : 'lessons'} · reviewed {formatDate(e.reviewed_at)}
						</p>
						<p class="mt-2 text-sm">{e.reason}</p>
						{#if e.teacher_comment}
							<p class="mt-2 rounded-lg bg-surface px-3 py-2 text-sm">
								<span class="font-medium">Your comment:</span> {e.teacher_comment}
							</p>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	</section>
{/if}