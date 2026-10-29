<script>
	import { enhance } from '$app/forms';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import { EXCUSE_STATUS, ABSENCE_LABEL, formatDay, formatTime, formatRange, groupByDate } from '$lib/excuses.js';

	let { data, form } = $props();

	let selected = $state([]); // ausgewählte attendance-IDs
	let sending = $state(false);

	const days = $derived(groupByDate(data.absences));

	// "Whole day": alle Stunden eines Tages an- bzw. abwählen
	function toggleDay(items) {
		const ids = items.map((a) => a.id);
		const all = ids.every((id) => selected.includes(id));
		selected = all ? selected.filter((id) => !ids.includes(id)) : [...new Set([...selected, ...ids])];
	}
</script>

<svelte:head>
	<title>Excuses · EduDevice</title>
</svelte:head>

<PageHeader title="Excuses" subtitle="Excuse your absences – your class teacher reviews them" />

<!-- Neue Entschuldigung -->
<section class="rounded-2xl border border-line bg-white p-6">
	<h2 class="text-lg font-semibold">Submit an excuse</h2>
	<p class="text-sm text-subtle">Select the lessons you missed and give a reason.</p>

	{#if days.length === 0}
		<div class="mt-5 flex items-center gap-3 rounded-xl bg-surface px-4 py-4 text-sm text-subtle">
			<Icon name="check" class="size-5 text-success" />
			You have no unexcused absences.
		</div>
	{:else}
		<form
			method="POST"
			action="?/submit"
			class="mt-5"
			use:enhance={() => {
				sending = true;
				return async ({ result, update }) => {
					await update({ reset: result.type === 'success' });
					if (result.type === 'success') selected = [];
					sending = false;
				};
			}}
		>
			<!-- Fehlstunden nach Tag -->
			<div class="space-y-4">
				{#each days as day (day.date)}
					<div class="rounded-xl border border-line">
						<div class="flex items-center justify-between border-b border-divider px-4 py-2.5">
							<p class="text-sm font-semibold">{formatDay(day.date)}</p>
							<button type="button" class="cursor-pointer text-xs font-medium text-accent hover:text-accent-darker"
								onclick={() => toggleDay(day.items)}>
								{day.items.every((a) => selected.includes(a.id)) ? 'Deselect day' : 'Whole day'}
							</button>
						</div>

						<ul class="divide-y divide-divider">
							{#each day.items as a (a.id)}
								<li>
									<label class="flex cursor-pointer items-center gap-3 px-4 py-3 transition hover:bg-surface">
										<input type="checkbox" name="attendance_ids" value={a.id} bind:group={selected}
											class="size-4 rounded border-input text-accent focus:ring-accent/30" />
										<span class="w-12 text-sm text-subtle tabular-nums">{formatTime(a.start_time)}</span>
										<span class="flex-1 text-sm font-medium">{a.subject}</span>
										<span class="rounded-full bg-surface px-2.5 py-0.5 text-xs font-medium text-subtle">
											{ABSENCE_LABEL[a.status] ?? a.status}
										</span>
									</label>
								</li>
							{/each}
						</ul>
					</div>
				{/each}
			</div>

			<!-- Begründung -->
			<div class="mt-5">
				<label for="reason" class="label">Reason</label>
				<textarea id="reason" name="reason" rows="3" required minlength="5" maxlength="1000"
					class="input resize-y" placeholder="e.g. I was sick with a fever"
					value={form?.reason ?? ''}></textarea>
			</div>

			<div class="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
				<p class="text-sm text-subtle">
					{selected.length} {selected.length === 1 ? 'lesson' : 'lessons'} selected
				</p>
				<button type="submit" class="btn-primary sm:w-auto sm:px-6" disabled={sending || selected.length === 0}>
					{sending ? 'Submitting…' : 'Submit excuse'}
				</button>
			</div>
		</form>
	{/if}

	{#if form?.error}
		<p class="mt-4 rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">{form.error}</p>
	{:else if form?.success}
		<p class="mt-4 rounded-lg border border-success/30 bg-success/10 px-4 py-3 text-sm text-success-dark">
			Your excuse has been sent to your class teacher.
		</p>
	{/if}
</section>

<!-- Eigene Entschuldigungen -->
<section class="mt-6 rounded-2xl border border-line bg-white p-6">
	<h2 class="text-lg font-semibold">My excuses</h2>

	{#if data.excuses.length === 0}
		<p class="mt-3 text-sm text-subtle">You haven't submitted any excuses yet.</p>
	{:else}
		<ul class="mt-4 divide-y divide-divider">
			{#each data.excuses as e (e.id)}
				<li class="py-4">
					<div class="flex flex-wrap items-center justify-between gap-2">
						<p class="font-semibold">{formatRange(e.date_from, e.date_to)}</p>
						<span class="rounded-full px-3 py-1 text-xs font-semibold {EXCUSE_STATUS[e.status].class}">
							{EXCUSE_STATUS[e.status].label}
						</span>
					</div>
					<p class="mt-1 text-xs text-subtle">
						{e.absences.length} {e.absences.length === 1 ? 'lesson' : 'lessons'}:
						{e.absences.map((a) => a.subject).join(', ')}
					</p>
					<p class="mt-2 text-sm">{e.reason}</p>

					{#if e.teacher_comment}
						<p class="mt-2 rounded-lg bg-surface px-3 py-2 text-sm">
							<span class="font-medium">Class teacher:</span> {e.teacher_comment}
						</p>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}
</section>