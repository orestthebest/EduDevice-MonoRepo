<script>
	import { enhance } from '$app/forms';
	import Icon from '$lib/components/Icon.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { formatDate } from '$lib/format.js';
	import { percent } from '$lib/quiz.js';
	import { m } from '$lib/paraglide/messages.js';

	let { data, form } = $props();

	const s = $derived(data.subject);
	let creating = $state(false);
</script>

<svelte:head>
	<title>{m.quizzes()} · {s.subject_name} · EduDevice</title>
</svelte:head>

<PageHeader title={m.quizzes()} subtitle="{s.subject_name} · {m.class_name({ name: s.class_name })}" back="/subjects/{s.id}" />

<div class="grid items-start gap-4 {data.isOwner ? 'lg:grid-cols-[1fr_340px]' : ''}">
	<section class="rounded-xl border border-line bg-white p-4 sm:p-5">
		<h2 class="mb-3 text-base font-semibold">{data.isOwner ? m.quiz_all() : m.quiz_yours()}</h2>

		{#if data.quizzes.length === 0}
			<p class="rounded-lg bg-surface px-3 py-6 text-center text-sm text-subtle">
				{data.isOwner ? m.quiz_none_owner() : m.quiz_none_student()}
			</p>
		{:else}
			<ul class="divide-y divide-divider">
				{#each data.quizzes as q (q.id)}
					<li class="flex flex-wrap items-center gap-3 py-3">
						<div class="min-w-0 flex-1">
							<div class="flex flex-wrap items-center gap-2">
								<p class="truncate text-sm font-medium">{q.title}</p>
								{#if data.isOwner}
									{#if q.is_published}
										<span class="rounded-md bg-success/12 px-2 py-0.5 text-xs font-medium text-success-dark">{m.quiz_published()}</span>
									{:else}
										<span class="rounded-md bg-surface px-2 py-0.5 text-xs font-medium text-subtle">{m.quiz_draft()}</span>
									{/if}
									{#if q.locked}
										<span class="rounded-md bg-warning/15 px-2 py-0.5 text-xs font-medium text-[#b4730f]">{m.quiz_locked()}</span>
									{/if}
								{/if}
							</div>
							<p class="text-xs text-subtle">
								{q.question_count} {q.question_count === 1 ? m.quiz_question() : m.quiz_questions()} · {q.max_score} {m.quiz_points()}
								{#if data.isOwner} · {q.attempt_count} {q.attempt_count === 1 ? m.quiz_submission() : m.quiz_submissions()} · {m.quiz_created({ date: formatDate(q.created_at) })}{/if}
								{#if q.description} · {q.description}{/if}
							</p>
						</div>

						{#if data.isOwner}
							<a href="/quizzes/{q.id}"
								class="inline-flex items-center gap-2 rounded-lg border border-ghost px-3 py-1.5 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
								{m.open()} <Icon name="arrow" />
							</a>
						{:else if q.my_result}
							<span class="rounded-md bg-accent-light px-2 py-0.5 text-xs font-semibold text-accent-dark">
								{q.my_result.score} / {q.my_result.max_score} · {percent(q.my_result.score, q.my_result.max_score)}%
							</span>
							<a href="/quizzes/{q.id}/take?s={s.id}"
								class="inline-flex items-center gap-2 rounded-lg border border-ghost px-3 py-1.5 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
								{m.quiz_view_result()}
							</a>
						{:else}
							<a href="/quizzes/{q.id}/take?s={s.id}"
								class="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent-dark">
								{m.quiz_start()} <Icon name="arrow" />
							</a>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	</section>

	{#if data.isOwner}
		<!-- Neues Quiz (nur Lehrer des Fachs) -->
		<section class="rounded-xl border border-line bg-white p-4 sm:p-5">
			<h2 class="text-base font-semibold">{m.quiz_new()}</h2>

			<form method="POST" action="?/create" class="mt-4 flex flex-col gap-4"
				use:enhance={() => {
					creating = true;
					return async ({ update }) => {
						await update();
						creating = false;
					};
				}}>
				{#if form?.error}
					<p class="rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">{form.error}</p>
				{/if}

				<div>
					<label for="title" class="label">{m.title()}</label>
					<input id="title" name="title" value={form?.title ?? ''} required maxlength="150" placeholder={m.quiz_title_placeholder()} class="input" />
				</div>
				<div>
					<label for="description" class="label">{m.description()} <span class="font-normal text-subtle">{m.optional()}</span></label>
					<input id="description" name="description" value={form?.description ?? ''} placeholder={m.quiz_desc_placeholder()} class="input" />
				</div>

				<button type="submit" disabled={creating}
					class="inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent-dark disabled:opacity-50">
					<Icon name="plus" /> {creating ? m.subj_creating() : m.quiz_create()}
				</button>
				<p class="text-xs text-subtle">{m.quiz_draft_hint()}</p>
			</form>
		</section>
	{/if}
</div>