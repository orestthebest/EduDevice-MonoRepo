<script>
	// Schülersicht auf die eigenen Noten (Ziel-M-3).
	//
	// Aufbau von oben nach unten: erst die eine Zahl, die zählt, dann der
	// Vergleich zwischen den Fächern, dann je Fach die Einzelheiten. Wer nur
	// wissen will „wie stehe ich da“, muss nicht scrollen.
	import PageHeader from '$lib/components/PageHeader.svelte';
	import SubjectBars from '$lib/components/SubjectBars.svelte';
	import TrendLine from '$lib/components/TrendLine.svelte';
	import ComponentBars from '$lib/components/ComponentBars.svelte';
	import { fmtGrade, standingOf, categoryLabel, shortDate } from '$lib/grades.js';

	let { data } = $props();
	let stats = $derived(data.stats);
	let overall = $derived(stats.overall);
	let passMark = $derived(stats.scale.pass_threshold);

	// Offenes Fach: standardmäßig das schwächste, weil es die Aufmerksamkeit
	// am ehesten braucht. Die API liefert bereits aufsteigend sortiert.
	let open = $state(0);
</script>

<svelte:head><title>My grades · EduDevice</title></svelte:head>

<PageHeader
	title={data.isOwnView ? 'My grades' : stats.student.name}
	subtitle="As of {new Date(stats.as_of).toLocaleDateString('en-GB', {
		day: 'numeric', month: 'long', year: 'numeric'
	})}"
/>

{#if stats.subjects.length === 0}
	<div class="rounded-2xl border border-line bg-white p-10 text-center">
		<p class="font-medium">No grades yet</p>
		<p class="mt-1 text-sm text-subtle">
			As soon as your teachers enter marks, your results appear here.
		</p>
	</div>
{:else}
	<!-- Kennzahlen: keine Diagramme, weil es einzelne Zahlen sind -->
	<div class="grid gap-4 sm:grid-cols-3">
		<div class="rounded-2xl border border-line bg-white p-5">
			<p class="text-xs font-medium tracking-wide text-subtle uppercase">Overall average</p>
			<div class="mt-2 flex items-baseline gap-2">
				<span class="font-heading text-4xl font-bold">{fmtGrade(overall.raw)}</span>
				{#if overall.rounded != null}
					<span class="text-sm text-subtle">rounds to {overall.rounded}</span>
				{/if}
			</div>
			<p class="mt-1 text-xs text-muted">
				across {overall.n_subjects} subject{overall.n_subjects === 1 ? '' : 's'} · scale 4–10, 10 is best
			</p>
		</div>

		<div class="rounded-2xl border border-line bg-white p-5">
			<p class="text-xs font-medium tracking-wide text-subtle uppercase">Needs attention</p>
			<div class="mt-2 flex items-baseline gap-2">
				<span class="font-heading text-4xl font-bold">{overall.n_at_risk}</span>
				<span class="text-sm text-subtle">below the pass mark</span>
			</div>
			<p class="mt-1 text-xs text-muted">
				{overall.n_fragile} more just above it
			</p>
		</div>

		<div class="rounded-2xl border border-line bg-white p-5">
			<p class="text-xs font-medium tracking-wide text-subtle uppercase">Pass mark</p>
			<div class="mt-2 flex items-baseline gap-2">
				<span class="font-heading text-4xl font-bold">{passMark}</span>
				<span class="text-sm text-subtle">rounds up to 5</span>
			</div>
			<p class="mt-1 text-xs text-muted">
				An average of {passMark} or more is a pass; {stats.scale.fragile_below} is the warning band.
			</p>
		</div>
	</div>

	<!-- Fächer im Vergleich -->
	<section class="mt-6 rounded-2xl border border-line bg-white p-5">
		<h2 class="mb-4 text-base font-semibold">Where you stand in each subject</h2>
		<SubjectBars subjects={stats.subjects} {passMark} />
	</section>

	<!-- Je Fach die Einzelheiten -->
	<section class="mt-6 space-y-3">
		<h2 class="text-base font-semibold">Subject by subject</h2>

		{#each stats.subjects as s, i}
			{@const st = standingOf(s.standing)}
			<article class="overflow-hidden rounded-2xl border border-line bg-white">
				<button
					type="button"
					class="flex w-full cursor-pointer items-center gap-4 p-5 text-left transition hover:bg-surface/60"
					onclick={() => (open = open === i ? -1 : i)}
					aria-expanded={open === i}
				>
					<div class="min-w-0 flex-1">
						<div class="flex flex-wrap items-center gap-2">
							<h3 class="truncate font-semibold">{s.subject_name}</h3>
							<span class="rounded-full px-2 py-0.5 text-[11px] font-medium {st.chip}">
								{st.label}
							</span>
							{#if s.current.provisional}
								<span class="rounded-full bg-surface px-2 py-0.5 text-[11px] text-subtle">
									provisional · {s.current.missing.join(', ')} missing
								</span>
							{/if}
						</div>
						<p class="mt-0.5 text-xs text-subtle">
							{s.class_name} · {s.n_marks} mark{s.n_marks === 1 ? '' : 's'}
							{#if s.class_comparison}
								· {s.class_comparison.delta >= 0 ? '+' : ''}{fmtGrade(s.class_comparison.delta, 2)}
								vs class average
							{/if}
						</p>
					</div>

					<div class="text-right">
						<div class="font-heading text-2xl font-bold">{fmtGrade(s.current.raw)}</div>
						{#if s.current.rounded != null}
							<div class="text-[11px] text-subtle">rounds to {s.current.rounded}</div>
						{/if}
					</div>
				</button>

				{#if open === i}
					<div class="border-t border-divider px-5 pt-5 pb-5">
						{#if s.required_remaining_avg != null}
							<!-- Die nützlichste Einzelzahl: sie benennt einen
							     Handlungsspielraum statt eines Urteils. -->
							<p
								class="mb-5 rounded-xl px-4 py-3 text-sm {s.reachable
									? 'bg-accent-light text-accent-dark'
									: 'bg-error/10 text-error'}"
							>
								{#if s.reachable}
									You need an average of
									<strong>{fmtGrade(s.required_remaining_avg)}</strong>
									on what is still open to pass this subject.
								{:else}
									Even a 10 on everything still open would not reach the pass mark here.
								{/if}
							</p>
						{/if}

						<div class="grid gap-6 lg:grid-cols-2">
							<div>
								<h4 class="mb-3 text-xs font-medium tracking-wide text-subtle uppercase">
									How the grade is made up
								</h4>
								<ComponentBars components={s.components} />
							</div>

							<div>
								<h4 class="mb-1 text-xs font-medium tracking-wide text-subtle uppercase">
									Across the trimesters
								</h4>
								{#if stats.has_trimesters}
									<TrendLine points={s.by_trimester} {passMark} />
								{:else}
									<p class="py-6 text-center text-xs text-muted">
										Trimester dates are not set up yet.
									</p>
								{/if}
							</div>
						</div>

						{#if s.recent.length}
							<h4 class="mt-6 mb-2 text-xs font-medium tracking-wide text-subtle uppercase">
								Latest marks
							</h4>
							<ul class="divide-y divide-divider text-sm">
								{#each s.recent as r}
									<li class="flex items-center justify-between py-2">
										<span>
											{categoryLabel(r.category)}
											<span class="ml-1.5 text-[11px] text-muted">
												{r.component}{r.weight !== 1 ? ` · weight ${r.weight}` : ''}
											</span>
										</span>
										<span class="flex items-center gap-3">
											<span class="text-xs text-muted">{shortDate(r.date)}</span>
											<span class="w-6 text-right font-semibold">{r.value}</span>
										</span>
									</li>
								{/each}
							</ul>
						{/if}
					</div>
				{/if}
			</article>
		{/each}
	</section>

	<p class="mt-6 text-xs text-muted">
		All figures are calculated from the individual marks your teachers entered, using the
		school's weighting of 40 % Mitarbeit, 40 % Schularbeit and 20 % Projekt. A component
		that has not been graded yet is left out of the calculation rather than counted as a
		zero. Class figures are averages only — you never see another student's marks.
	</p>
{/if}
