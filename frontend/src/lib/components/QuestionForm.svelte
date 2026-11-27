<script>
	import { untrack } from 'svelte';
	import { enhance } from '$app/forms';
	import Icon from '$lib/components/Icon.svelte';
	import { TYPE_LABEL, gapIndexes } from '$lib/quiz.js';
	import { m } from '$lib/paraglide/messages.js';

	// question = bestehende Frage (bearbeiten) oder null (neue Frage)
	// onDone   = wird nach dem Speichern oder bei "Cancel" aufgerufen
	let { question = null, onDone } = $props();

	// Startwerte einmalig aus der Frage (Format von GET /quizzes/{id}) holen.
	// Die Elternseite erzeugt das Formular mit {#key} neu, wenn eine andere Frage bearbeitet wird.
	const start = untrack(() => {
		const q = question;
		const opts = q?.options ?? [];
		return {
			type: q?.type ?? 'mc',
			text: q?.question_text ?? '',
			points: q?.points ?? 1,
			options:
				q?.type === 'mc'
					? opts.map((o) => ({ text: o.option_text, correct: o.is_correct }))
					: [{ text: '', correct: true }, { text: '', correct: false }],
			tfCorrect: q?.type === 'tf' ? (opts.find((o) => o.option_text === 'Wahr')?.is_correct ?? true) : true,
			// Lücke -> akzeptierte Antworten mit ";" getrennt, z.B. "0,75; 0.75"
			gaps:
				q?.type === 'gap'
					? gapIndexes(q.question_text)
							.sort((a, b) => a - b)
							.map((gi) => opts.filter((o) => o.gap_index === gi).map((o) => o.option_text).join('; '))
					: []
		};
	});

	let type = $state(start.type);
	let text = $state(start.text);
	let points = $state(start.points);
	let options = $state(start.options);
	let tfCorrect = $state(start.tfCorrect);
	let gaps = $state(start.gaps);
	let textArea = $state();
	let showError = $state(false);
	let saving = $state(false);

	const gapNumbers = $derived(gapIndexes(text).sort((a, b) => a - b));

	// Lücke {{n}} an der Cursor-Position einfügen
	function insertGap() {
		const tag = `{{${gapNumbers.length}}}`;
		const pos = textArea?.selectionStart ?? text.length;
		text = text.slice(0, pos) + tag + text.slice(pos);
	}

	// Gleiche Regeln wie die API -> Fehler schon vor dem Absenden anzeigen
	const problem = $derived.by(() => {
		if (!text.trim()) return m.quiz_err_q_text();
		if (!Number.isInteger(points) || points < 1 || points > 100) return m.quiz_err_points();
		if (type === 'mc') {
			const filled = options.filter((o) => o.text.trim());
			if (filled.length < 2) return m.quiz_err_two_answers();
			if (!filled.some((o) => o.correct)) return m.quiz_err_one_correct();
		}
		if (type === 'gap') {
			if (gapNumbers.length === 0) return m.quiz_err_no_gap();
			if (!gapNumbers.every((n, i) => n === i)) return m.quiz_err_gap_numbers({ example: '{{0}}, {{1}}, {{2}} …' });
			if (gapNumbers.some((i) => !splitAnswers(gaps[i]).length)) return m.quiz_err_gap_answer();
		}
		return '';
	});

	const splitAnswers = (value) => (value ?? '').split(';').map((a) => a.trim()).filter(Boolean);

	// Body für POST /quizzes/{id}/questions bzw. PUT /questions/{id} (siehe QUIZ_API.md)
	const payload = $derived.by(() => {
		const base = { type, question_text: text.trim(), points };
		if (type === 'mc')
			return { ...base, options: options.filter((o) => o.text.trim()).map((o) => ({ option_text: o.text.trim(), is_correct: o.correct })) };
		if (type === 'tf') return { ...base, correct: tfCorrect };
		return { ...base, gaps: gapNumbers.map((i) => splitAnswers(gaps[i])) };
	});
</script>

<form
	method="POST"
	action="?/saveQuestion"
	class="flex flex-col gap-3"
	use:enhance={({ cancel }) => {
		if (problem) {
			showError = true;
			cancel();
			return;
		}
		saving = true;
		return async ({ result, update }) => {
			await update({ reset: false });
			saving = false;
			if (result.type === 'success') onDone();
		};
	}}
>
	<input type="hidden" name="question_id" value={question?.id ?? ''} />
	<input type="hidden" name="payload" value={JSON.stringify(payload)} />

	<!-- Fragetyp -->
	<div class="grid grid-cols-3 gap-0.5 rounded-lg border border-line bg-surface p-0.5">
		{#each Object.entries(TYPE_LABEL) as [key, label] (key)}
			<button type="button" onclick={() => (type = key)}
				class="cursor-pointer rounded-md px-2 py-1.5 text-xs font-medium transition
				{type === key ? 'bg-white text-accent-dark shadow-sm' : 'text-subtle hover:text-navy'}">
				{label}
			</button>
		{/each}
	</div>

	<div>
		<div class="mb-1.5 flex items-end justify-between gap-2">
			<label for="q-text" class="text-sm font-medium">{type === 'tf' ? m.quiz_statement() : m.quiz_question_label()}</label>
			{#if type === 'gap'}
				<button type="button" onclick={insertGap}
					class="inline-flex cursor-pointer items-center gap-1 rounded-lg border border-ghost px-2 py-1 text-xs font-medium transition hover:border-accent hover:text-accent-dark">
					<Icon name="plus" class="size-3.5" /> {m.quiz_insert_gap()}
				</button>
			{/if}
		</div>
		<textarea id="q-text" bind:this={textArea} bind:value={text} rows="3" class="input resize-y"
			placeholder={type === 'gap' ? m.quiz_ph_gap({ gap: '{{0}}' }) : type === 'tf' ? m.quiz_ph_tf() : m.quiz_ph_mc()}
		></textarea>
	</div>

	{#if type === 'mc'}
		<div>
			<p class="label">{m.quiz_answers()} <span class="font-normal text-subtle">{m.quiz_tick_correct()}</span></p>
			<div class="flex flex-col gap-2">
				{#each options as option, i (i)}
					<div class="flex items-center gap-2">
						<input type="checkbox" bind:checked={option.correct} aria-label={m.quiz_answer_correct({ n: i + 1 })}
							class="size-5 cursor-pointer rounded border-input text-success focus:ring-success/30" />
						<input bind:value={option.text} placeholder={m.quiz_answer_n({ n: i + 1 })} class="input py-2" />
						<button type="button" onclick={() => options.splice(i, 1)} disabled={options.length <= 2}
							class="grid size-8 shrink-0 cursor-pointer place-items-center rounded-lg border border-ghost text-subtle transition hover:border-error hover:text-error disabled:cursor-not-allowed disabled:opacity-40"
							aria-label={m.quiz_remove_answer({ n: i + 1 })}>
							<Icon name="x" />
						</button>
					</div>
				{/each}
			</div>
			<button type="button" onclick={() => options.push({ text: '', correct: false })}
				class="mt-2 inline-flex cursor-pointer items-center gap-1 text-sm font-medium text-accent-dark hover:text-accent-darker">
				<Icon name="plus" /> {m.quiz_add_answer()}
			</button>
		</div>
	{:else if type === 'tf'}
		<div>
			<p class="label">{m.quiz_correct_answer()}</p>
			<div class="grid grid-cols-2 gap-2">
				{#each [[true, m.quiz_true()], [false, m.quiz_false()]] as [value, label] (label)}
					<button type="button" onclick={() => (tfCorrect = value)}
						class="cursor-pointer rounded-lg border px-4 py-2 text-sm font-medium transition
						{tfCorrect === value ? 'border-success bg-success/12 text-success-dark' : 'border-ghost hover:border-accent'}">
						{label}
					</button>
				{/each}
			</div>
		</div>
	{:else}
		<div>
			<p class="label">{m.quiz_accepted()} <span class="font-normal text-subtle">{m.quiz_separate()}</span></p>
			{#if gapNumbers.length === 0}
				<p class="rounded-lg bg-surface px-3 py-3 text-center text-xs text-subtle">{m.quiz_gap_click_hint()}</p>
			{:else}
				<div class="flex flex-col gap-2">
					{#each gapNumbers as n (n)}
						<div class="flex items-center gap-2">
							<span class="shrink-0 rounded-md bg-accent-light px-2 py-1 font-mono text-xs text-accent-dark">{`{{${n}}}`}</span>
							<input bind:value={gaps[n]} placeholder={m.quiz_ph_gap_answers()} class="input py-2" />
						</div>
					{/each}
				</div>
				<p class="mt-2 text-xs text-subtle">{m.quiz_case_hint()}</p>
			{/if}
		</div>
	{/if}

	<div class="w-28">
		<label for="q-points" class="label">{m.quiz_points_label()}</label>
		<input id="q-points" type="number" min="1" max="100" step="1" bind:value={points} class="input py-2" />
	</div>

	{#if showError && problem}
		<p class="rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">{problem}</p>
	{/if}

	<div class="flex gap-2">
		{#if question}
			<button type="button" onclick={onDone}
				class="cursor-pointer rounded-lg border border-ghost px-4 py-2 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
				{m.cancel()}
			</button>
		{/if}
		<button type="submit" disabled={saving}
			class="inline-flex flex-1 cursor-pointer items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent-dark disabled:opacity-50">
			{#if !question}<Icon name="plus" />{/if}
			{saving ? m.saving() : question ? m.quiz_save_question() : m.quiz_add_question()}
		</button>
	</div>
</form>