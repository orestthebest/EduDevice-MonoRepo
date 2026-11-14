<script>
	// Schülersicht auf die eigenen Noten (Ziel-M-3), Version 2.
	//
	// Aufbau von oben nach unten:
	//   1. Gesamtschnitt im Banner (gleicher Verlauf wie das Begrüßungs-Banner
	//      des Dashboards) - die eine Zahl, die zählt
	//   2. Hinweise, falls ein Fach Aufmerksamkeit braucht
	//   3. Neueste Noten über alle Fächer + Beobachtungen der Woche
	//   4. Die Fächer, schwächstes zuerst, aufklappbar
	//   5. "How grades work" - die Regeln (Bestehensgrenze 4,6 usw.) als Info
	//
	// Gerechnet wird nichts: alle Zahlen und Hinweise kommen fertig aus der API.
	import PageHeader from '$lib/components/PageHeader.svelte';
	import Sparkline from '$lib/components/Sparkline.svelte';
	import TrendLine from '$lib/components/TrendLine.svelte';
	import ComponentBars from '$lib/components/ComponentBars.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import { fmtGrade, fmtSigned, standingOf, categoryLabel, shortDate } from '$lib/grades.js';

	let { data } = $props();
	let stats = $derived(data.stats);
	let overall = $derived(stats.overall);
	let passMark = $derived(stats.scale.pass_threshold);
	let notices = $derived(stats.notices ?? []);
	let recent = $derived(stats.recent_overall ?? []);
	let insights = $derived(stats.insights ?? []);
	let serious = $derived(notices.some((n) => n.kind !== 'fragile'));

	// Offenes Fach: standardmäßig das schwächste (die API sortiert aufsteigend)
	let open = $state(0);
	let rulesOpen = $state(false);

	function openSubject(csId) {
		open = stats.subjects.findIndex((s) => s.class_subject_id === csId);
	}

	const TONE = {
		positive: { icon: 'check', box: 'bg-success/12 text-success-dark' },
		neutral: { icon: 'arrow', box: 'bg-accent-light text-accent-dark' },
		attention: { icon: 'clipboard', box: 'bg-warning/15 text-[#b4730f]' }
	};
</script>

<svelte:head><title>My grades · EduDevice</title></svelte:head>

<PageHeader
	title={data.isOwnView ? 'My grades' : stats.student.name}
	subtitle="As of {new Date(stats.as_of).toLocaleDateString('en-GB', {
		day: 'numeric',
		month: 'long',
		year: 'numeric'
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
	<!-- 1. Gesamtschnitt -->
	<section
		class="grid gap-6 rounded-2xl border border-sidebar-border bg-dash-gradient px-6 py-6 sm:px-8 md:grid-cols-[1fr_auto] md:items-center"
	>
		<div>
			<p class="text-sm font-semibold text-accent-dark">Overall average</p>
			<div class="mt-1 flex items-baseline gap-3">
				<span class="font-heading text-5xl font-bold tabular-nums">{fmtGrade(overall.raw)}</span>
				{#if overall.rounded != null}
					<span class="text-subtle"
						>rounds to <strong class="text-navy">{overall.rounded}</strong></span
					>
				{/if}
			</div>
			<p class="mt-2 text-sm text-subtle">
				Across {overall.n_subjects} subject{overall.n_subjects === 1 ? '' : 's'} ·
				<a
					href="#how-grades-work"
					onclick={() => (rulesOpen = true)}
					class="font-medium text-accent-dark underline-offset-2 hover:text-accent-darker hover:underline"
				>
					How grades work
				</a>
			</p>
		</div>

		<div class="grid grid-cols-3 gap-2 sm:gap-3">
			{#each [['ok', overall.n_ok], ['fragile', overall.n_fragile], ['failing', overall.n_at_risk]] as [key, n]}
				{@const st = standingOf(key)}
				<div class="rounded-xl bg-white/70 px-3 py-3 sm:min-w-28 sm:px-4">
					<p class="font-heading text-2xl font-bold tabular-nums">{n}</p>
					<p class="mt-0.5 flex items-center gap-1.5 text-xs text-subtle">
						<span class="size-2 shrink-0 rounded-full {st.dot}"></span>{st.label}
					</p>
				</div>
			{/each}
		</div>
	</section>

	<!-- 2. Hinweise: was Aufmerksamkeit braucht -->
	{#if notices.length}
		<section
			class="mt-6 rounded-2xl border p-5 sm:p-6 {serious
				? 'border-error/30 bg-error/[0.04]'
				: 'border-warning/40 bg-warning/[0.06]'}"
		>
			<h2 class="text-lg font-semibold">Needs your attention</h2>
			<ul class="mt-3 space-y-2.5">
				{#each notices as n (n.class_subject_id)}
					{@const st = standingOf(n.kind === 'unreachable' ? 'failing' : n.kind)}
					<li class="flex items-start gap-3 text-sm">
						<span class="mt-0.5 shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold {st.chip}"
							>{st.label}</span
						>
						<p class="flex-1">
							<strong>{n.subject_name}</strong>
							{#if n.kind === 'unreachable'}
								— even a 10 on everything still open would not reach the pass mark. Talk to your
								teacher about what can still be done.
							{:else if n.kind === 'failing'}
								is below the pass mark at {fmtGrade(n.current)}.
								{#if n.required_remaining_avg != null}
									You need an average of <strong>{fmtGrade(n.required_remaining_avg)}</strong> on what's
									still open to pass.
								{/if}
							{:else if n.secured}
								is close to the line at {fmtGrade(n.current)}, but already safe: even 4s on
								everything still open would pass.
							{:else}
								is close to the line at {fmtGrade(n.current)}.
								{#if n.required_remaining_avg != null}
									An average of <strong>{fmtGrade(n.required_remaining_avg)}</strong> on what's still
									open keeps you above it.
								{/if}
							{/if}
						</p>
						<a
							href="#cs-{n.class_subject_id}"
							onclick={() => openSubject(n.class_subject_id)}
							class="shrink-0 text-sm font-medium text-accent-dark hover:text-accent-darker">View</a
						>
					</li>
				{/each}
			</ul>
		</section>
	{/if}

	<!-- 3. Neueste Noten + Beobachtungen der Woche -->
	<div class="mt-6 grid gap-6 lg:grid-cols-5">
		<section class="rounded-2xl border border-line bg-white p-5 sm:p-6 lg:col-span-3">
			<h2 class="text-lg font-semibold">Recent grades</h2>
			<p class="text-sm text-subtle">Your newest marks across all subjects</p>
			{#if recent.length === 0}
				<p class="mt-4 rounded-xl bg-surface px-4 py-6 text-center text-sm text-subtle">
					No marks yet.
				</p>
			{:else}
				<ul class="mt-3 divide-y divide-divider">
					{#each recent as r}
						<li class="flex items-center gap-3 py-2.5">
							<span
								class="grid size-10 shrink-0 place-items-center rounded-xl bg-surface font-heading text-lg font-bold tabular-nums"
							>
								{fmtGrade(r.value, 1)}
							</span>
							<div class="min-w-0 flex-1">
								<p class="flex items-center gap-2 truncate text-sm font-semibold">
									{r.subject_name}
									{#if r.is_new}
										<span
											class="rounded-full bg-accent-light px-2 py-0.5 text-[11px] font-semibold text-accent-dark"
											>New</span
										>
									{/if}
								</p>
								<p class="truncate text-xs text-subtle">
									{categoryLabel(r.category)}{r.weight !== 1 ? ` · weight ${r.weight}` : ''} · {shortDate(
										r.date
									)}
								</p>
							</div>
							<!-- Wirkung auf den Fachschnitt: Vorzeichen + Text, Farbe nur zusätzlich -->
							<span
								class="shrink-0 text-right text-xs tabular-nums
								{r.effect > 0 ? 'text-success-dark' : r.effect < 0 ? 'text-error' : 'text-muted'}"
							>
								{#if r.effect == null}
									first mark
								{:else if r.effect === 0}
									no change
								{:else}
									<span class="font-semibold">{fmtSigned(r.effect)}</span>
									<span class="block text-[11px] text-muted">to average</span>
								{/if}
							</span>
						</li>
					{/each}
				</ul>
			{/if}
		</section>

		<section class="rounded-2xl border border-line bg-white p-5 sm:p-6 lg:col-span-2">
			<h2 class="text-lg font-semibold">What we noticed</h2>
			<p class="text-sm text-subtle">This week in your marks</p>
			{#if insights.length === 0}
				<p class="mt-4 rounded-xl bg-surface px-4 py-6 text-sm text-subtle">
					Every week, up to three things that stand out in your marks show up here — what's going
					well and what has changed.
				</p>
			{:else}
				<ul class="mt-3 space-y-3">
					{#each insights as i}
						{@const tone = TONE[i.tone] ?? TONE.neutral}
						<li class="flex gap-3">
							<span class="grid size-8 shrink-0 place-items-center rounded-lg {tone.box}">
								<Icon name={tone.icon} />
							</span>
							<p class="text-sm">
								{#if i.subject_name}<span class="font-semibold">{i.subject_name}:</span>{/if}
								{i.message}
							</p>
						</li>
					{/each}
				</ul>
			{/if}
		</section>
	</div>

	<!-- 4. Die Fächer -->
	<section class="mt-6">
		<div class="mb-3 flex items-baseline justify-between">
			<h2 class="text-lg font-semibold">Subjects</h2>
			<p class="text-xs text-muted">weakest first · line = your average over the year</p>
		</div>

		<div class="space-y-3">
			{#each stats.subjects as s, i (s.class_subject_id)}
				{@const st = standingOf(s.standing)}
				<article
					id="cs-{s.class_subject_id}"
					class="scroll-mt-6 overflow-hidden rounded-2xl border border-line bg-white"
				>
					<button
						type="button"
						class="flex w-full cursor-pointer items-center gap-4 p-4 text-left transition hover:bg-surface/60 sm:p-5"
						onclick={() => (open = open === i ? -1 : i)}
						aria-expanded={open === i}
					>
						<span class="h-10 w-1 shrink-0 rounded-full {st.dot}" aria-hidden="true"></span>
						<div class="min-w-0 flex-1">
							<div class="flex flex-wrap items-center gap-2">
								<h3 class="truncate font-semibold">{s.subject_name}</h3>
								<span class="rounded-full px-2.5 py-0.5 text-xs font-semibold {st.chip}"
									>{st.label}</span
								>
								{#if s.current.provisional}
									<span class="rounded-full bg-surface px-2 py-0.5 text-[11px] text-subtle">
										provisional · {s.current.missing.join(', ')} missing
									</span>
								{/if}
							</div>
							<p class="mt-0.5 text-xs text-subtle">
								{s.class_name} · {s.n_marks} mark{s.n_marks === 1 ? '' : 's'}
								{#if s.class_comparison}
									· {fmtSigned(s.class_comparison.delta)} vs class average
								{/if}
							</p>
						</div>

						<div class="hidden sm:block">
							<Sparkline points={s.progression ?? []} {passMark} />
						</div>

						<div class="w-16 text-right">
							<div class="font-heading text-2xl font-bold tabular-nums">
								{fmtGrade(s.current.raw)}
							</div>
							{#if s.current.rounded != null}
								<div class="text-[11px] text-subtle">rounds to {s.current.rounded}</div>
							{/if}
						</div>
						<span class="text-muted transition {open === i ? '-rotate-90' : 'rotate-180'}">
							<Icon name="back" />
						</span>
					</button>

					{#if open === i}
						<div class="border-t border-divider p-4 sm:p-5">
							{#if s.required_remaining_avg != null}
								<!-- Handlungsspielraum statt Urteil -->
								<p
									class="mb-5 rounded-xl px-4 py-3 text-sm {!s.reachable
										? 'bg-error/10 text-error'
										: s.secured
											? 'bg-success/12 text-success-dark'
											: 'bg-accent-light text-accent-dark'}"
								>
									{#if !s.reachable}
										Even a 10 on everything still open would not reach the pass mark here.
									{:else if s.secured}
										Already safe: even 4s on everything still open would pass this subject.
									{:else}
										You need an average of <strong>{fmtGrade(s.required_remaining_avg)}</strong>
										on what is still open to pass this subject.
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
												<span class="w-8 text-right font-semibold tabular-nums"
													>{fmtGrade(r.value, 1)}</span
												>
											</span>
										</li>
									{/each}
								</ul>
							{/if}
						</div>
					{/if}
				</article>
			{/each}
		</div>
	</section>

	<!-- 5. Die Regeln als Info statt als eigene Kachel -->
	<details
		id="how-grades-work"
		bind:open={rulesOpen}
		class="mt-6 scroll-mt-6 rounded-2xl border border-line bg-white"
	>
		<summary class="flex cursor-pointer list-none items-center justify-between p-5 font-semibold">
			How grades work
			<span class="text-muted transition {rulesOpen ? '-rotate-90' : 'rotate-180'}"
				><Icon name="back" /></span
			>
		</summary>
		<ul class="space-y-2 border-t border-divider p-5 text-sm text-subtle">
			<li>Grades run from <strong class="text-navy">4 to 10</strong>; 10 is the best.</li>
			<li>
				The pass mark is <strong class="text-navy">{passMark}</strong>. Averages round up only from
				.6: 4.6 becomes a 5 (pass), 4.5 becomes a 4 (fail).
			</li>
			<li>
				A subject grade is <strong class="text-navy">40 % Mitarbeit</strong>,
				<strong class="text-navy">40 % Schularbeit</strong>
				and <strong class="text-navy">20 % Projekt</strong>. A part that has not been graded yet is
				left out rather than counted as zero — the grade is then marked as provisional.
			</li>
			<li>"Close to the line" means passing, but below {stats.scale.fragile_below}.</li>
			<li>Class figures are averages only. You never see another student's marks.</li>
		</ul>
	</details>
{/if}
