<script>
	import { enhance } from '$app/forms';
	import Icon from '$lib/components/Icon.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { formatDate } from '$lib/format.js';
	import { TYPE_LABEL, optionLabel, splitGaps, percent } from '$lib/quiz.js';

	let { data, form } = $props();

	// Ergebnis: direkt nach dem Abgeben (form) oder beim erneuten Öffnen (data)
	const result = $derived(form?.result ?? data.result);
	// Fragen gibt es nur, solange die Seite offen ist (die API liefert sie nach der Abgabe nicht mehr)
	const questions = $derived(data.quiz?.questions ?? []);
	const title = $derived(data.quiz?.title ?? 'Quiz result');

	let submitting = $state(false);

	const hint = { mc: 'Select all correct answers', tf: 'Choose one', gap: 'Type the missing words' };
</script>

<svelte:head>
	<title>{title} · EduDevice</title>
</svelte:head>

<PageHeader {title} subtitle={data.quiz?.description ?? ''} back={data.back} />

{#if result}
	<!-- Ergebnis -->
	<section class="bg-dash-gradient mb-6 rounded-2xl border border-line p-6 sm:p-8">
		<p class="text-sm font-medium text-subtle">Your result</p>
		<p class="mt-1 text-4xl font-bold">
			{result.score} <span class="text-2xl text-subtle">/ {result.max_score} points</span>
		</p>
		<div class="mt-4 h-2.5 overflow-hidden rounded-full bg-white/70">
			<div class="h-full rounded-full bg-accent" style="width: {percent(result.score, result.max_score)}%"></div>
		</div>
		<p class="mt-2 text-sm text-subtle">
			{percent(result.score, result.max_score)}% · {result.questions.filter((q) => q.correct).length} of {result.questions.length} questions correct · submitted {formatDate(result.submitted_at)}
		</p>
	</section>

	<section class="rounded-2xl border border-line bg-white p-6">
		<h2 class="mb-4 text-lg font-semibold">Questions</h2>
		<ol class="divide-y divide-divider">
			{#each result.questions as r, i (r.question_id)}
				{@const text = r.question_text ?? questions.find((x) => x.id === r.question_id)?.question_text}
				<li class="flex items-center gap-3 py-3">
					<span class="grid size-7 shrink-0 place-items-center rounded-lg text-xs font-bold {r.correct ? 'bg-success/12 text-success-dark' : 'bg-error/10 text-error'}">
						{r.correct ? '✓' : '✗'}
					</span>
					<p class="min-w-0 flex-1 truncate">
						<span class="font-medium">Question {i + 1}</span>
								{#if text}<span class="text-subtle"> · {text.replace(/\{\{\d+\}\}/g, '___')}</span>{/if}
					</p>
					<span class="shrink-0 text-sm font-medium {r.correct ? 'text-success-dark' : 'text-subtle'}">
						{r.points_awarded} {r.points_awarded === 1 ? 'point' : 'points'}
					</span>
				</li>
			{/each}
		</ol>
	</section>
{:else}
	<!-- Quiz lösen -->
	<form method="POST" action="?/submit" class="flex flex-col gap-4"
		use:enhance={({ cancel }) => {
			if (!confirm('Submit your answers? You can only submit once.')) return cancel();
			submitting = true;
			return async ({ update }) => {
				// Seite nicht neu laden, damit die Fragen fürs Ergebnis erhalten bleiben
				await update({ reset: false, invalidateAll: false });
				submitting = false;
				window.scrollTo({ top: 0, behavior: 'smooth' });
			};
		}}>
		{#if form?.error}
			<p class="rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">{form.error}</p>
		{/if}

		{#each questions as q, i (q.id)}
			<fieldset class="rounded-2xl border border-line bg-white p-6">
				<legend class="sr-only">Question {i + 1}</legend>
				<p class="text-xs text-subtle">
					Question {i + 1} of {questions.length} · {q.points} {q.points === 1 ? 'point' : 'points'} · {TYPE_LABEL[q.type]} – {hint[q.type]}
				</p>

				{#if q.type === 'gap'}
					<p class="mt-2 leading-10 font-medium">
						{#each splitGaps(q.question_text) as part, p (p)}
							{#if part.gap !== undefined}
								<input name="gap_{q.id}_{part.gap}" autocomplete="off" aria-label="Gap {part.gap + 1}"
									class="mx-1 inline-block w-36 rounded-lg border-input px-3 py-1.5 text-sm focus:border-accent focus:ring-4 focus:ring-accent/15" />
							{:else}{part.text}{/if}
						{/each}
					</p>
				{:else}
					<p class="mt-2 font-medium">{q.question_text}</p>
					<div class="mt-4 grid gap-2 {q.type === 'tf' ? 'grid-cols-2' : ''}">
						{#each q.options as o (o.id)}
							<label class="flex cursor-pointer items-center gap-3 rounded-xl border border-line px-4 py-3 transition hover:border-accent has-[:checked]:border-accent has-[:checked]:bg-accent-xlight">
								<input type={q.type === 'mc' ? 'checkbox' : 'radio'} name="opt_{q.id}" value={o.id}
									class="size-4 cursor-pointer border-input text-accent focus:ring-accent/30 {q.type === 'mc' ? 'rounded' : ''}" />
								<span>{optionLabel(o.option_text)}</span>
							</label>
						{/each}
					</div>
				{/if}
			</fieldset>
		{/each}

		<div class="flex items-center justify-between gap-4 rounded-2xl border border-line bg-white p-4">
			<p class="text-sm text-subtle">{questions.length} questions · {data.quiz.max_score} points · you can submit only once</p>
			<button type="submit" disabled={submitting}
				class="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white transition hover:bg-accent-dark disabled:opacity-50">
				{submitting ? 'Submitting…' : 'Submit'} <Icon name="arrow" />
			</button>
		</div>
	</form>
{/if}