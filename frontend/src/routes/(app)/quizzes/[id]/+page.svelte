<script>
	import { enhance } from '$app/forms';
	import Icon from '$lib/components/Icon.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import QuestionForm from '$lib/components/QuestionForm.svelte';
	import { formatDate } from '$lib/format.js';
	import { TYPE_LABEL, optionLabel, splitGaps, percent } from '$lib/quiz.js';

	let { data, form } = $props();

	const quiz = $derived(data.quiz);
	const subtitle = $derived(
		`${quiz.is_published ? 'Published' : 'Draft'} · ${quiz.questions.length} ${quiz.questions.length === 1 ? 'question' : 'questions'} · ${quiz.max_score} points`
	);

	// Tabs: "questions" oder "results"
	let tab = $state('questions');

	// Welche Frage wird gerade bearbeitet? null = rechts steht "Neue Frage"
	let editing = $state(null);
	let formKey = $state(0); // erhöhen = Formular neu aufbauen (leeren)
	function edit(question) {
		editing = question;
		formKey++;
	}
	function doneEditing() {
		editing = null;
		formKey++;
	}

	// Durchschnitt aller Abgaben in Prozent
	const average = $derived(
		data.attempts.length
			? Math.round(data.attempts.reduce((sum, a) => sum + percent(a.score, a.max_score), 0) / data.attempts.length)
			: 0
	);

	let confirmDialog = $state();
	let deleting = $state(false);
</script>

<svelte:head>
	<title>{quiz.title} · EduDevice</title>
</svelte:head>

<PageHeader title={quiz.title} {subtitle} back="/subjects/{quiz.class_subject_id}/quizzes">
	<form method="POST" action="?/publish" use:enhance>
		<input type="hidden" name="publish" value={!quiz.is_published} />
		<button type="submit" disabled={!quiz.is_published && quiz.questions.length === 0}
			title={!quiz.is_published && quiz.questions.length === 0 ? 'Add a question first' : ''}
			class="inline-flex h-10 cursor-pointer items-center gap-2 rounded-xl px-4 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50
			{quiz.is_published ? 'border border-line bg-white text-subtle hover:border-accent hover:text-accent-dark' : 'bg-accent text-white hover:bg-accent-dark'}">
			{quiz.is_published ? 'Hide from students' : 'Publish'}
		</button>
	</form>
	{#if !quiz.locked}
		<button type="button" onclick={() => confirmDialog.showModal()}
			class="inline-flex h-10 cursor-pointer items-center gap-2 rounded-xl border border-line bg-white px-4 text-sm font-medium text-subtle transition hover:border-error hover:text-error">
			<Icon name="trash" /> Delete
		</button>
	{/if}
</PageHeader>

{#if form?.error}
	<p class="mb-5 rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">{form.error}</p>
{:else if form?.saved}
	<p class="mb-5 rounded-lg border border-success/30 bg-success/12 px-4 py-3 text-sm text-success-dark">{form.saved}</p>
{/if}

{#if quiz.locked}
	<p class="mb-5 rounded-lg border border-warning/40 bg-warning/12 px-4 py-3 text-sm text-[#8a5a0c]">
		Students have already submitted this quiz, so questions can no longer be changed. You can still hide or publish it.
	</p>
{/if}

<!-- Tabs: Questions | Results -->
<div class="mb-5 inline-flex gap-1 rounded-xl border border-line bg-white p-1">
	{#each [['questions', 'Questions', quiz.questions.length], ['results', 'Results', data.attempts.length]] as [key, label, count] (key)}
		<button type="button" onclick={() => (tab = key)}
			class="inline-flex cursor-pointer items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition
			{tab === key ? 'bg-accent text-white' : 'text-subtle hover:bg-surface hover:text-navy'}">
			{label}
			<span class="rounded-full px-2 py-0.5 text-xs {tab === key ? 'bg-white/20' : 'bg-surface'}">{count}</span>
		</button>
	{/each}
</div>

{#if tab === 'questions'}
	<div class="grid items-start gap-6 {quiz.locked ? '' : 'lg:grid-cols-[1fr_380px]'}">
		<!-- Fragenliste mit Lösungen -->
		<section class="rounded-2xl border border-line bg-white p-6">
			<h2 class="mb-4 text-lg font-semibold">Questions</h2>

			{#if quiz.questions.length === 0}
				<p class="rounded-xl bg-surface px-4 py-10 text-center text-sm text-subtle">No questions yet. Add the first one on the right.</p>
			{:else}
				<ol class="flex flex-col gap-3">
					{#each quiz.questions as q, i (q.id)}
						<li class="rounded-xl border p-4 {editing?.id === q.id ? 'border-accent bg-accent-xlight' : 'border-line'}">
							<div class="flex items-start gap-3">
								<span class="grid size-7 shrink-0 place-items-center rounded-lg bg-surface text-xs font-bold">{i + 1}</span>
								<div class="min-w-0 flex-1">
									<p class="text-xs text-subtle">{TYPE_LABEL[q.type]} · {q.points} {q.points === 1 ? 'point' : 'points'}</p>
									<p class="mt-1 font-medium">
										{#each splitGaps(q.question_text) as part, p (p)}
											{#if part.gap !== undefined}
												<span class="mx-0.5 rounded bg-accent-light px-1.5 text-accent-dark">{q.options.filter((o) => o.gap_index === part.gap).map((o) => o.option_text).join(' / ')}</span>
											{:else}{part.text}{/if}
										{/each}
									</p>
									{#if q.type !== 'gap'}
										<ul class="mt-2 flex flex-wrap gap-1.5">
											{#each q.options as o (o.id)}
												<li class="rounded-lg border px-2.5 py-1 text-sm {o.is_correct ? 'border-success/40 bg-success/12 text-success-dark' : 'border-line text-subtle'}">
													{o.is_correct ? '✓ ' : ''}{optionLabel(o.option_text)}
												</li>
											{/each}
										</ul>
									{/if}
								</div>

								{#if !quiz.locked}
									<div class="flex shrink-0 gap-1.5">
										<button type="button" onclick={() => edit(q)}
											class="cursor-pointer rounded-lg border border-ghost px-3 py-1.5 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
											Edit
										</button>
										<form method="POST" action="?/deleteQuestion" use:enhance={() => async ({ update }) => {
											await update();
											if (editing?.id === q.id) doneEditing();
										}}>
											<input type="hidden" name="question_id" value={q.id} />
											<button type="submit" aria-label="Delete question {i + 1}"
												class="grid size-9 cursor-pointer place-items-center rounded-lg border border-ghost text-subtle transition hover:border-error hover:text-error">
												<Icon name="trash" />
											</button>
										</form>
									</div>
								{/if}
							</div>
						</li>
					{/each}
				</ol>
			{/if}
		</section>

		{#if !quiz.locked}
			<div class="flex flex-col gap-6">
				<!-- Frage anlegen / bearbeiten -->
				<section class="rounded-2xl border border-line bg-white p-6">
					<h2 class="mb-4 text-lg font-semibold">
						{editing ? `Edit question ${quiz.questions.findIndex((q) => q.id === editing.id) + 1}` : 'New question'}
					</h2>
					{#key formKey}
						<QuestionForm question={editing} onDone={doneEditing} />
					{/key}
				</section>

				<!-- Titel + Beschreibung -->
				<section class="rounded-2xl border border-line bg-white p-6">
					<h2 class="mb-4 text-lg font-semibold">Details</h2>
					<form method="POST" action="?/details" class="flex flex-col gap-4" use:enhance={() => async ({ update }) => update({ reset: false })}>
						<div>
							<label for="title" class="label">Title</label>
							<input id="title" name="title" value={quiz.title} required maxlength="150" class="input" />
						</div>
						<div>
							<label for="description" class="label">Description <span class="font-normal text-subtle">(optional)</span></label>
							<input id="description" name="description" value={quiz.description ?? ''} class="input" />
						</div>
						<button type="submit"
							class="cursor-pointer rounded-lg border border-ghost px-4 py-2.5 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
							Save details
						</button>
					</form>
				</section>
			</div>
		{/if}
	</div>
{:else}
	<!-- Ergebnisse aller Schüler -->
	<section class="rounded-2xl border border-line bg-white p-6">
		<div class="mb-4 flex flex-wrap items-baseline justify-between gap-2">
			<h2 class="text-lg font-semibold">Results</h2>
			{#if data.attempts.length}
				<p class="text-sm text-subtle">Average: <span class="font-semibold text-navy">{average}%</span></p>
			{/if}
		</div>

		{#if data.attempts.length === 0}
			<p class="rounded-xl bg-surface px-4 py-10 text-center text-sm text-subtle">
				{quiz.is_published ? 'No student has submitted yet.' : 'Publish the quiz so students can take it.'}
			</p>
		{:else}
			<ul class="divide-y divide-divider">
				{#each [...data.attempts].sort((a, b) => a.last_name.localeCompare(b.last_name)) as a (a.student_id)}
					<li class="flex items-center gap-3 py-3">
						<span class="bg-brand-gradient grid size-9 shrink-0 place-items-center rounded-full text-xs font-semibold text-white">
							{(a.first_name[0] + a.last_name[0]).toUpperCase()}
						</span>
						<div class="min-w-0 flex-1">
							<p class="truncate font-medium">{a.first_name} {a.last_name}</p>
							<p class="text-xs text-subtle">{a.username} · submitted {formatDate(a.submitted_at)}</p>
						</div>
						<span class="rounded-full bg-accent-light px-3 py-1 text-sm font-semibold text-accent-dark">
							{a.score} / {a.max_score} · {percent(a.score, a.max_score)}%
						</span>
					</li>
				{/each}
			</ul>
		{/if}
	</section>
{/if}

<!-- Bestätigungs-Dialog: Quiz löschen -->
<dialog bind:this={confirmDialog}
	class="m-auto w-full max-w-sm rounded-2xl border border-line bg-white p-0 text-navy shadow-xl backdrop:bg-navy/35">
	<form method="POST" action="?/deleteQuiz" class="p-6"
		use:enhance={() => {
			deleting = true;
			return async ({ update }) => {
				await update();
				deleting = false;
				confirmDialog?.close(); // bei Fehler steht die Meldung oben auf der Seite
			};
		}}>
		<input type="hidden" name="class_subject_id" value={quiz.class_subject_id} />
		<span class="grid size-11 place-items-center rounded-xl bg-error/12 text-error">
			<Icon name="trash" class="size-5" />
		</span>
		<h2 class="mt-4 text-lg font-bold">Delete "{quiz.title}"?</h2>
		<p class="mt-1 text-sm text-subtle">The quiz and all its questions are removed. This cannot be undone.</p>

		<div class="mt-6 flex justify-end gap-2">
			<button type="button" onclick={() => confirmDialog.close()}
				class="cursor-pointer rounded-lg border border-ghost px-4 py-2.5 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
				Cancel
			</button>
			<button type="submit" disabled={deleting}
				class="cursor-pointer rounded-lg bg-error px-4 py-2.5 text-sm font-medium text-white transition hover:bg-error/90 disabled:opacity-60">
				{deleting ? 'Deleting…' : 'Delete'}
			</button>
		</div>
	</form>
</dialog>