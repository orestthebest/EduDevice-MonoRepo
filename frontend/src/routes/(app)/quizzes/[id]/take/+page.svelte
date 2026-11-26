<script>
	import { enhance } from '$app/forms';
	import Icon from '$lib/components/Icon.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { formatDate } from '$lib/format.js';
	import { TYPE_LABEL, optionLabel, splitGaps, percent } from '$lib/quiz.js';
	import { m } from '$lib/paraglide/messages.js';

	let { data, form } = $props();

	// Ergebnis: direkt nach dem Abgeben (form) oder beim erneuten Öffnen (data)
	const result = $derived(form?.result ?? data.result);
	// Fragen gibt es nur, solange die Seite offen ist (die API liefert sie nach der Abgabe nicht mehr)
	const questions = $derived(data.quiz?.questions ?? []);
	const title = $derived(data.quiz?.title ?? m.quiz_result_title());

	let submitting = $state(false);

	// Bestätigungs-Dialog vor dem Abgeben (statt Browser-confirm)
	let submitDialog = $state();
	let quizForm = $state();
	let confirmed = false;
	let answered = $state(0);

	// Wie viele Fragen haben mindestens eine Antwort?
	function countAnswered() {
		const entries = [...new FormData(quizForm).entries()];
		return questions.filter((q) =>
			entries.some(([k, v]) => (k === `opt_${q.id}` || k.startsWith(`gap_${q.id}_`)) && String(v).trim() !== '')
		).length;
	}

	const hint = { mc: m.quiz_hint_mc, tf: m.quiz_hint_tf, gap: m.quiz_hint_gap };
</script>

<svelte:head>
	<title>{title} · EduDevice</title>
</svelte:head>

<PageHeader {title} subtitle={data.quiz?.description ?? ''} back={data.back} />

{#if result}
	<!-- Ergebnis -->
	<section class="bg-dash-gradient mb-6 rounded-2xl border border-line p-6 sm:p-8">
		<p class="text-sm font-medium text-subtle">{m.quiz_your_result()}</p>
		<p class="mt-1 text-4xl font-bold">
			{result.score} <span class="text-2xl text-subtle">/ {result.max_score} {m.quiz_points()}</span>
		</p>
		<div class="mt-4 h-2.5 overflow-hidden rounded-full bg-white/70">
			<div class="h-full rounded-full bg-accent" style="width: {percent(result.score, result.max_score)}%"></div>
		</div>
		<p class="mt-2 text-sm text-subtle">
			{percent(result.score, result.max_score)}% · {m.quiz_correct_summary({ correct: result.questions.filter((q) => q.correct).length, total: result.questions.length })} · {m.quiz_submitted({ date: formatDate(result.submitted_at) })}
		</p>
	</section>

	<section class="rounded-2xl border border-line bg-white p-6">
		<h2 class="mb-4 text-lg font-semibold">{m.quiz_tab_questions()}</h2>
		<ol class="divide-y divide-divider">
			{#each result.questions as r, i (r.question_id)}
				{@const text = r.question_text ?? questions.find((x) => x.id === r.question_id)?.question_text}
				<li class="flex items-center gap-3 py-3">
					<span class="grid size-7 shrink-0 place-items-center rounded-lg text-xs font-bold {r.correct ? 'bg-success/12 text-success-dark' : 'bg-error/10 text-error'}">
						{r.correct ? '✓' : '✗'}
					</span>
					<p class="min-w-0 flex-1 truncate">
						<span class="font-medium">{m.quiz_question_n({ n: i + 1 })}</span>
								{#if text}<span class="text-subtle"> · {text.replace(/\{\{\d+\}\}/g, '___')}</span>{/if}
					</p>
					<span class="shrink-0 text-sm font-medium {r.correct ? 'text-success-dark' : 'text-subtle'}">
						{r.points_awarded} {r.points_awarded === 1 ? m.quiz_point() : m.quiz_points()}
					</span>
				</li>
			{/each}
		</ol>
	</section>
{:else}
	<!-- Quiz lösen -->
	<form method="POST" action="?/submit" class="flex flex-col gap-4" bind:this={quizForm}
		use:enhance={({ cancel }) => {
			// 1. Klick auf "Submit": nur den Dialog öffnen
			if (!confirmed) {
				cancel();
				answered = countAnswered();
				submitDialog.showModal();
				return;
			}
			// 2. Im Dialog bestätigt: wirklich abschicken
			confirmed = false;
			submitDialog.close();
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
				<legend class="sr-only">{m.quiz_question_n({ n: i + 1 })}</legend>
				<p class="text-xs text-subtle">
					{m.quiz_question_of({ n: i + 1, total: questions.length })} · {q.points} {q.points === 1 ? m.quiz_point() : m.quiz_points()} · {TYPE_LABEL[q.type]} – {hint[q.type]()}
				</p>

				{#if q.type === 'gap'}
					<p class="mt-2 leading-10 font-medium">
						{#each splitGaps(q.question_text) as part, p (p)}
							{#if part.gap !== undefined}
								<input name="gap_{q.id}_{part.gap}" autocomplete="off" aria-label={m.quiz_gap_n({ n: part.gap + 1 })}
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
			<p class="text-sm text-subtle">{questions.length} {m.quiz_questions()} · {data.quiz.max_score} {m.quiz_points()} · {m.quiz_submit_once()}</p>
			<button type="submit" disabled={submitting}
				class="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white transition hover:bg-accent-dark disabled:opacity-50">
				{submitting ? m.quiz_submitting() : m.quiz_submit()} <Icon name="arrow" />
			</button>
		</div>
	</form>

		<!-- Bestätigungs-Dialog: Quiz abgeben -->
	<dialog bind:this={submitDialog}
		class="m-auto w-full max-w-sm rounded-2xl border border-line bg-white p-0 text-navy shadow-xl backdrop:bg-navy/35">
		<div class="p-6">
			<span class="grid size-11 place-items-center rounded-xl bg-accent-light text-accent-dark">
				<Icon name="check" class="size-5" />
			</span>
			<h2 class="mt-4 text-lg font-bold">{m.quiz_submit_title()}</h2>
			<p class="mt-1 text-sm text-subtle">{m.quiz_submit_text()}</p>

			<p class="mt-4 rounded-lg px-4 py-3 text-sm
				{answered < questions.length ? 'border border-warning/40 bg-warning/10 text-navy' : 'bg-surface text-subtle'}">
				{m.quiz_answered({ answered, total: questions.length })}
				{#if answered < questions.length}· {m.quiz_still_empty({ count: questions.length - answered })}{/if}
			</p>

			<div class="mt-6 flex justify-end gap-2">
				<button type="button" onclick={() => submitDialog.close()}
					class="cursor-pointer rounded-lg border border-ghost px-4 py-2.5 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
					{m.quiz_keep_working()}
				</button>
				<button type="button" onclick={() => { confirmed = true; quizForm.requestSubmit(); }}
					class="cursor-pointer rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white transition hover:bg-accent-dark">
					{m.quiz_submit()}
				</button>
			</div>
		</div>
	</dialog>
{/if}