<script>
	import { enhance } from '$app/forms';
	import Icon from '$lib/components/Icon.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { formatDate } from '$lib/format.js';
	import { percent } from '$lib/quiz.js';

	let { data, form } = $props();

	const s = $derived(data.subject);
	let creating = $state(false);
</script>

<svelte:head>
	<title>Quizzes · {s.subject_name} · EduDevice</title>
</svelte:head>

<PageHeader title="Quizzes" subtitle="{s.subject_name} · Class {s.class_name}" back="/subjects/{s.id}" />

<div class="grid items-start gap-6 {data.isOwner ? 'lg:grid-cols-[1fr_340px]' : ''}">
	<section class="rounded-2xl border border-line bg-white p-6">
		<h2 class="mb-4 text-lg font-semibold">{data.isOwner ? 'All quizzes' : 'Your quizzes'}</h2>

		{#if data.quizzes.length === 0}
			<p class="rounded-xl bg-surface px-4 py-10 text-center text-sm text-subtle">
				{data.isOwner ? 'No quizzes yet. Create one on the right.' : 'No quizzes available yet.'}
			</p>
		{:else}
			<ul class="divide-y divide-divider">
				{#each data.quizzes as q (q.id)}
					<li class="flex flex-wrap items-center gap-4 py-4">
						<div class="min-w-0 flex-1">
							<div class="flex flex-wrap items-center gap-2">
								<p class="truncate font-medium">{q.title}</p>
								{#if data.isOwner}
									{#if q.is_published}
										<span class="rounded-full bg-success/12 px-2 py-0.5 text-xs font-medium text-success-dark">Published</span>
									{:else}
										<span class="rounded-full bg-surface px-2 py-0.5 text-xs font-medium text-subtle">Draft</span>
									{/if}
									{#if q.locked}
										<span class="rounded-full bg-warning/15 px-2 py-0.5 text-xs font-medium text-[#b4730f]">Locked</span>
									{/if}
								{/if}
							</div>
							<p class="text-xs text-subtle">
								{q.question_count} {q.question_count === 1 ? 'question' : 'questions'} · {q.max_score} points
								{#if data.isOwner} · {q.attempt_count} {q.attempt_count === 1 ? 'submission' : 'submissions'} · created {formatDate(q.created_at)}{/if}
								{#if q.description} · {q.description}{/if}
							</p>
						</div>

						{#if data.isOwner}
							<a href="/quizzes/{q.id}"
								class="inline-flex items-center gap-2 rounded-lg border border-ghost px-3 py-1.5 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
								Open <Icon name="arrow" />
							</a>
						{:else if q.my_result}
							<span class="rounded-full bg-accent-light px-3 py-1 text-sm font-semibold text-accent-dark">
								{q.my_result.score} / {q.my_result.max_score} · {percent(q.my_result.score, q.my_result.max_score)}%
							</span>
							<a href="/quizzes/{q.id}/take?s={s.id}"
								class="inline-flex items-center gap-2 rounded-lg border border-ghost px-3 py-1.5 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
								View result
							</a>
						{:else}
							<a href="/quizzes/{q.id}/take?s={s.id}"
								class="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent-dark">
								Start <Icon name="arrow" />
							</a>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	</section>

	{#if data.isOwner}
		<!-- Neues Quiz (nur Lehrer des Fachs) -->
		<section class="rounded-2xl border border-line bg-white p-6">
			<h2 class="text-lg font-semibold">New quiz</h2>

			<form method="POST" action="?/create" class="mt-4 flex flex-col gap-4"
				use:enhance={() => {
					creating = true;
					return async ({ update }) => {
						await update();
						creating = false;
					};
				}}>
				{#if form?.error}
					<p class="rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">{form.error}</p>
				{/if}

				<div>
					<label for="title" class="label">Title</label>
					<input id="title" name="title" value={form?.title ?? ''} required maxlength="150" placeholder="e.g. Fractions" class="input" />
				</div>
				<div>
					<label for="description" class="label">Description <span class="font-normal text-subtle">(optional)</span></label>
					<input id="description" name="description" value={form?.description ?? ''} placeholder="e.g. Chapter 4" class="input" />
				</div>

				<button type="submit" disabled={creating}
					class="inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white transition hover:bg-accent-dark disabled:opacity-50">
					<Icon name="plus" /> {creating ? 'Creating…' : 'Create quiz'}
				</button>
				<p class="text-xs text-subtle">The quiz stays a draft until you publish it.</p>
			</form>
		</section>
	{/if}
</div>