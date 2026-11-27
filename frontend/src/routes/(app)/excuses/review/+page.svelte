<script>
	import { enhance } from '$app/forms';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import { EXCUSE_STATUS, ABSENCE_LABEL, formatDay, formatRange } from '$lib/excuses.js';
	import { periodLabel } from '$lib/timetable.js';
	import { formatDate } from '$lib/format.js';
	import Attachments from '$lib/components/Attachments.svelte';
	import { m } from '$lib/paraglide/messages.js';

	let { data, form } = $props();

	let tab = $state('pending'); // 'pending' | 'reviewed'
	let busyId = $state(null); // Entschuldigung, die gerade gespeichert wird
</script>

<svelte:head>
	<title>{m.nav_excuse_review()} · EduDevice</title>
</svelte:head>

<PageHeader title={m.nav_excuse_review()} subtitle={m.rev_subtitle()} />

<!-- Tabs -->
<div class="mb-3 inline-flex rounded-lg border border-line bg-white p-0.5">
	{#each [['pending', `${m.excuse_pending()} (${data.pending.length})`], ['reviewed', m.rev_history()]] as [key, label] (key)}
		<button
			type="button"
			class="cursor-pointer rounded-md px-3 py-1.5 text-sm font-medium transition
			{tab === key ? 'bg-accent-light text-accent-dark' : 'text-subtle hover:text-navy'}"
			onclick={() => (tab = key)}
		>
			{label}
		</button>
	{/each}
</div>

{#if form?.success}
	<p class="mb-4 rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-sm text-success-dark">{form.success}</p>
{/if}

{#if tab === 'pending'}
	{#if data.pending.length === 0}
		<section class="flex items-center gap-3 rounded-xl border border-line bg-white p-4 sm:p-5 text-sm text-subtle">
			<Icon name="check" class="size-5 text-success" />
			{m.dash_no_pending()}
		</section>
	{:else}
		<div class="space-y-3">
			{#each data.pending as e (e.id)}
				<section class="rounded-xl border border-line bg-white p-4 sm:p-5">
					<!-- Kopf: Schüler, Klasse, Zeitraum -->
					<div class="flex flex-wrap items-start justify-between gap-2">
						<div>
							<h2 class="text-base font-semibold">{e.student_name}</h2>
							<p class="text-sm text-subtle">
								{m.class_name({ name: e.class_name })} · {formatRange(e.date_from, e.date_to)} · {m.quiz_submitted({ date: formatDate(e.submitted_at) })}
							</p>
						</div>
						<span class="rounded-md px-2 py-0.5 text-xs font-semibold {EXCUSE_STATUS.pending.class}">
							{EXCUSE_STATUS.pending.label}
						</span>
					</div>

					<!-- Betroffene Stunden -->
					<ul class="mt-3 divide-y divide-divider rounded-lg border border-line">
						{#each e.absences as a (a.attendance_id)}
							<li class="flex items-center gap-3 px-3 py-2 text-sm">
								<span class="w-28 text-subtle">{formatDay(a.date)}</span>
								<span class="w-24 shrink-0 text-subtle">{periodLabel(a.start_time)}</span>
								<span class="flex-1 font-medium">{a.subject_name}</span>
								<!-- Badge nur, wenn es nicht einfach "abwesend" ist (z. B. verspätet) -->
								{#if a.status !== 'abwesend'}
									<span class="rounded-md bg-warning/15 px-2 py-0.5 text-xs font-medium text-[#b4730f]">
										{ABSENCE_LABEL[a.status] ?? a.status}
									</span>
								{/if}
							</li>
						{/each}
					</ul>

					<!-- Begründung des Schülers -->
					<p class="mt-3 text-xs font-medium text-subtle">{m.exc_reason()}</p>
					<p class="mt-1 text-sm">{e.reason}</p>

					
					<!-- Anhänge des Schülers (z. B. Arztbestätigung) -->
					{#if e.attachments?.length}
						<p class="mt-3 text-xs font-medium text-subtle">{m.exc_attachments()}</p>
						<Attachments excuseId={e.id} attachments={e.attachments} />
					{/if}

					<!-- Entscheidung -->
					<form
						method="POST"
						action="?/review"
						class="mt-3"
						use:enhance={() => {
							busyId = e.id;
							return async ({ update }) => {
								await update();
								busyId = null;
							};
						}}
					>
						<input type="hidden" name="id" value={e.id} />
						<label for="comment-{e.id}" class="label">{m.rev_comment()} <span class="font-normal text-subtle">{m.rev_comment_hint()}</span></label>
						<textarea id="comment-{e.id}" name="comment" rows="2" maxlength="500" class="input resize-y"
							placeholder={m.rev_comment_placeholder()}
							value={form?.id === e.id ? (form.comment ?? '') : ''}></textarea>

						{#if form?.error && form?.id === e.id}
							<p class="mt-3 rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">{form.error}</p>
						{/if}

						<div class="mt-3 flex flex-col gap-2 sm:flex-row sm:justify-end">
							<button type="submit" name="status" value="rejected" disabled={busyId === e.id}
								class="cursor-pointer rounded-lg border border-ghost px-4 py-2 text-sm font-medium transition hover:border-error hover:text-error">
								{m.rev_reject()}
							</button>
							<button type="submit" name="status" value="accepted" disabled={busyId === e.id}
								class="btn-primary text-sm sm:w-auto sm:px-5">
								{busyId === e.id ? m.saving() : m.rev_accept()}
							</button>
						</div>
					</form>
				</section>
			{/each}
		</div>
	{/if}
{:else}
	<!-- Bereits entschiedene Entschuldigungen -->
	<section class="rounded-xl border border-line bg-white p-4 sm:p-5">
		{#if data.reviewed.length === 0}
			<p class="text-sm text-subtle">{m.rev_none_reviewed()}</p>
		{:else}
			<ul class="divide-y divide-divider">
				{#each data.reviewed as e (e.id)}
					<li class="py-3 first:pt-0 last:pb-0">
						<div class="flex flex-wrap items-center justify-between gap-2">
							<p class="text-sm font-semibold">
								{e.student_name}
								<span class="font-normal text-subtle">· {e.class_name}</span>
							</p>
							<span class="rounded-md px-2 py-0.5 text-xs font-semibold {EXCUSE_STATUS[e.status].class}">
								{EXCUSE_STATUS[e.status].label}
							</span>
						</div>
						<p class="mt-1 text-xs text-subtle">
							{formatRange(e.date_from, e.date_to)} · {e.absences.length}
							{e.absences.length === 1 ? m.exc_lesson() : m.exc_lessons()} · {m.rev_reviewed({ date: formatDate(e.reviewed_at) })}
						</p>
						<p class="mt-1 text-sm">{e.reason}</p>

						<Attachments excuseId={e.id} attachments={e.attachments ?? []} />

						{#if e.teacher_comment}
							<p class="mt-2 rounded-lg bg-surface px-3 py-2 text-sm">
								<span class="font-medium">{m.rev_your_comment()}</span> {e.teacher_comment}
							</p>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	</section>
{/if}