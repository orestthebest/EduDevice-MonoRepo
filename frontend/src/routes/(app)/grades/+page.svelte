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
	// V3: Fehlzeiten je Fach (Budget bis 20 % / 30 % des Jahres) und
	// Hinweise, wenn ein Fach die Grenzen erreicht oder im Tempo darauf zuläuft.
	// Entwicklung je Fach (Rising / Steady / ...) und der noch mögliche Bereich
	// der Endnote aus dem nächtlichen Lauf. Die Ausfallwahrscheinlichkeit des
	// Modells liefert die API nur an Lehrkräfte - für Schüler fehlt das Feld.
	//
	// V4: Die Jahresnote wird je Trimester gerechnet (in der API). Der mögliche
	// Bereich kommt live aus der API (offen: kommende Trimester, der Rest des
	// laufenden, fehlende Teile); darin der wahrscheinliche Bereich (80 %)
	// aus dem Prognosemodell - für Schüler und Lehrkräfte. Erklärungen stehen
	// in Hinweisen (ⓘ) statt als Text unter jedem Element. Die Zeitleiste zeigt
	// den Schnitt über das ganze Jahr statt nur den Stand je Trimester.
	//
	// Gerechnet wird nichts: alle Zahlen und Hinweise kommen fertig aus der API.
		import PageHeader from '$lib/components/PageHeader.svelte';
	import Sparkline from '$lib/components/Sparkline.svelte';
	import GradeTimeline from '$lib/components/GradeTimeline.svelte';
	import ComponentBars from '$lib/components/ComponentBars.svelte';
	import AbsenceBudget from '$lib/components/AbsenceBudget.svelte';
	import RangeBar from '$lib/components/RangeBar.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import Tip from '$lib/components/Tip.svelte';
	import { fmtGrade, fmtSigned, standingOf, categoryLabel, shortDate } from '$lib/grades.js';
	import { m } from '$lib/paraglide/messages.js';
	import { getLocale } from '$lib/paraglide/runtime.js';

	let { data } = $props();
	let stats = $derived(data.stats);
	let overall = $derived(stats.overall);
	let passMark = $derived(stats.scale.pass_threshold);
	let notices = $derived(stats.notices ?? []);
	let recent = $derived(stats.recent_overall ?? []);
	let insights = $derived(stats.insights ?? []);
	let serious = $derived(notices.some((n) => !['fragile', 'absence_trend'].includes(n.kind)));

	// Kennzeichen der Hinweise: Notenstand oder Fehlzeiten
	function noticeChip(kind) {
		if (kind === 'absence_trend') return { label: m.grades_absence(), chip: standingOf('fragile').chip };
		if (kind.startsWith('absence')) return { label: m.grades_absence(), chip: standingOf('failing').chip };
		return standingOf(kind === 'unreachable' ? 'failing' : kind);
	}
	// Entwicklung der Noten: beschreibt die Noten, nicht den Menschen
	const GROWTH = {
		rising: { sign: '↗', label: m.growth_rising() },
		steady: { sign: '→', label: m.growth_steady() },
		falling: { sign: '↘', label: m.growth_falling() },
		up_and_down: { sign: '↕', label: m.growth_up_down() },
		too_early: { sign: '·', label: m.growth_too_early() }
	};
	let growthSummary = $derived(
		Object.entries(overall.growth ?? {})
			.filter(([key, n]) => n > 0 && key !== 'too_early')
			.map(([key, n]) => `${n} ${GROWTH[key].label.toLowerCase()}`)
			.join(' · ')
	);
	const when = (iso) =>
		new Date(iso).toLocaleString(getLocale(), {
			day: 'numeric',
			month: 'short',
			hour: '2-digit',
			minute: '2-digit'
		});
	const pct = (rate, digits = 1) => `${(rate * 100).toFixed(digits).replace(/\.0$/, '')} %`;

	// Offenes Fach: standardmäßig das schwächste (die API sortiert aufsteigend)
	let open = $state(0);
	let rulesOpen = $state(false);

	function openSubject(csId) {
		open = stats.subjects.findIndex((s) => s.class_subject_id === csId);
	}

	// Beobachtungen: Farbe nach Ton (gut / neutral / Achtung)
	const TONE = {
		positive: {
			card: 'border-success/25 bg-success/[0.06]',
			box: 'bg-success/15 text-success-dark',
			remark: 'text-success-dark'
		},
		neutral: {
			card: 'border-accent/15 bg-accent-xlight',
			box: 'bg-accent-light text-accent-dark',
			remark: 'text-accent-dark'
		},
		attention: {
			card: 'border-warning/30 bg-warning/[0.07]',
			box: 'bg-warning/20 text-[#b4730f]',
			remark: 'text-[#b4730f]'
		}
	};
	// je Art: Icon, Stichwort (Hinweis beim Icon) und eine kurze, freundliche
	// Bemerkung vorne - auch bei den Achtung-Punkten ermutigend, nie ein Urteil
	const INSIGHT = {
		recent_lift: { icon: 'trend-up', keyword: m.ins_kw_recent_lift(), remark: m.ins_nice() },
		good_mark: { icon: 'star', keyword: m.ins_kw_good_mark(), remark: m.ins_well_done() },
		streak: { icon: 'zap', keyword: m.ins_kw_streak(), remark: m.ins_keep_it_up() },
		trimester_up: { icon: 'trend-up', keyword: m.ins_kw_trimester_up(), remark: m.ins_getting_there() },
		attendance_clean: { icon: 'check', keyword: m.ins_kw_attendance_clean(), remark: m.ins_nice() },
		near_round_up: { icon: 'target', keyword: m.ins_kw_near_round_up(), remark: m.ins_so_close() },
		trimester_down: {
			icon: 'trend-down',
			keyword: m.ins_kw_trimester_down(),
			remark: m.ins_turn_around()
		},
		unusual_drop: {
			icon: 'trend-down',
			keyword: m.ins_kw_unusual_drop(),
			remark: m.ins_not_whole_story()
		},
		absence_pace: { icon: 'clock', keyword: m.ins_kw_absence_pace(), remark: m.ins_still_time() }
	};
	const failTone = (p) =>
		p >= 0.5
			? 'bg-error/10 text-error'
			: p >= 0.2
				? 'bg-warning/15 text-[#b4730f]'
				: 'bg-surface text-navy';
</script>

<svelte:head><title>{m.nav_my_grades()} · EduDevice</title></svelte:head>

<PageHeader
	title={data.isOwnView ? m.nav_my_grades() : stats.student.name}
	subtitle={m.grades_as_of({
		date: new Date(stats.as_of).toLocaleDateString(getLocale(), {
			day: 'numeric',
			month: 'long',
			year: 'numeric'
		})
	})}
/>

{#if stats.subjects.length === 0}
	<div class="rounded-2xl border border-line bg-white p-10 text-center">
		{#if !data.isOwnView && data.user.role === 'lehrkraft'}
			<!-- Lehrkräfte sehen nur ihre eigenen Fächer -->
			<p class="font-medium">{m.grades_none_teacher_title()}</p>
			<p class="mt-1 text-sm text-subtle">
				{m.grades_none_teacher_text({ name: stats.student.name })}
			</p>
		{:else}
			<p class="font-medium">{m.grades_none_title()}</p>
			<p class="mt-1 text-sm text-subtle">
				{m.grades_none_text()}
			</p>
		{/if}
	</div>
{:else}
	<!-- 1. Gesamtschnitt -->
	<section
		class="grid gap-6 rounded-2xl border border-sidebar-border bg-dash-gradient px-6 py-6 sm:px-8 md:grid-cols-[1fr_auto] md:items-center"
	>
		<div>
			<p class="text-sm font-semibold text-accent-dark">{m.grades_overall()}</p>
			<div class="mt-1 flex items-baseline gap-3">
				<span class="font-heading text-5xl font-bold tabular-nums">{fmtGrade(overall.raw)}</span>
				{#if overall.rounded != null}
					<span class="text-subtle"
						>{m.grades_rounds_to()} <strong class="text-navy">{overall.rounded}</strong></span
					>
				{/if}
			</div>
			<p class="mt-2 text-sm text-subtle">
				{overall.n_subjects === 1 ? m.grades_across_one({ n: overall.n_subjects }) : m.grades_across_many({ n: overall.n_subjects })} ·
				{#if overall.attendance}
					{m.grades_missed_pct({ rate: pct(overall.attendance.rate) })} ·
				{/if}
				<a
					href="#how-grades-work"
					onclick={() => (rulesOpen = true)}
					class="font-medium text-accent-dark underline-offset-2 hover:text-accent-darker hover:underline"
				>
					{m.grades_how_work()}
				</a>
			</p>
			{#if growthSummary}
				<p class="mt-1 text-sm text-subtle">{m.grades_your_marks({ summary: growthSummary })}</p>
			{/if}
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
			<h2 class="text-lg font-semibold">{m.grades_attention()}</h2>
			<ul class="mt-3 space-y-2.5">
				{#each notices as n (`${n.kind}-${n.class_subject_id}`)}
					{@const st = noticeChip(n.kind)}
					<li class="flex items-start gap-3 text-sm">
						<span class="mt-0.5 shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold {st.chip}"
							>{st.label}</span
						>
						<p class="flex-1">
							<strong>{n.subject_name}</strong>
							{#if n.kind === 'absence_fail'}
								{m.notice_absence_fail({ rate: pct(n.rate) })}
							{:else if n.kind === 'absence_exam'}
								{m.notice_absence_exam({ rate: pct(n.rate) })}
							{:else if n.kind === 'absence_trend'}
								{m.notice_absence_trend({ rate: pct(n.projected_rate, 0) })}
							{:else if n.kind === 'unreachable'}
								{m.notice_unreachable()}
							{:else if n.kind === 'failing'}
								{m.notice_failing({ grade: fmtGrade(n.current) })}
								{#if n.required_remaining_avg != null}
									{m.notice_need_before()} <strong>{fmtGrade(n.required_remaining_avg)}</strong>
									{m.notice_need_after()}
								{/if}
							{:else if n.secured}
								{m.notice_secured({ grade: fmtGrade(n.current) })}
							{:else}
								{m.notice_close({ grade: fmtGrade(n.current) })}
								{#if n.required_remaining_avg != null}
									{m.notice_keep_before()} <strong>{fmtGrade(n.required_remaining_avg)}</strong>
									{m.notice_keep_after()}
								{/if}
							{/if}
						</p>
						<a
							href="#cs-{n.class_subject_id}"
							onclick={() => openSubject(n.class_subject_id)}
							class="shrink-0 text-sm font-medium text-accent-dark hover:text-accent-darker">{m.grades_view()}</a
						>
					</li>
				{/each}
			</ul>
		</section>
	{/if}

	<!-- 3. Neueste Noten + Beobachtungen der Woche -->
	<div class="mt-6 grid gap-6 lg:grid-cols-5">
		<section class="rounded-2xl border border-line bg-white p-5 sm:p-6 lg:col-span-3">
			<h2 class="text-lg font-semibold">{m.grades_recent()}</h2>
			<p class="text-sm text-subtle">{m.grades_recent_sub()}</p>
			{#if recent.length === 0}
				<p class="mt-4 rounded-xl bg-surface px-4 py-6 text-center text-sm text-subtle">
					{m.grades_no_marks_yet()}.
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
											>{m.grades_new()}</span
										>
									{/if}
								</p>
								<p class="truncate text-xs text-subtle">
									{categoryLabel(r.category)}{r.weight !== 1 ? ` · ${m.grades_weight({ w: r.weight })}` : ''} · {shortDate(
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
									{m.grades_first_mark()}
								{:else if r.effect === 0}
									{m.grades_no_change()}
								{:else}
									<span class="font-semibold">{fmtSigned(r.effect)}</span>
									<span class="block text-[11px] text-muted">{m.grades_to_average()}</span>
								{/if}
							</span>
						</li>
					{/each}
				</ul>
			{/if}
		</section>

		<section class="rounded-2xl border border-line bg-white p-5 sm:p-6 lg:col-span-2">
			<h2 class="text-lg font-semibold">{m.grades_noticed()}</h2>
			<p class="text-sm text-subtle">{m.grades_noticed_sub()}</p>
			{#if insights.length === 0}
				<p class="mt-4 rounded-xl bg-surface px-4 py-6 text-sm text-subtle">
					{m.grades_noticed_empty()}
				</p>
			{:else}
				<ul class="mt-3 space-y-2.5">
					{#each insights as i}
						{@const tone = TONE[i.tone] ?? TONE.neutral}
						{@const kind = INSIGHT[i.kind] ?? { icon: 'arrow', keyword: '', remark: '' }}
						<li class="flex items-start gap-3 rounded-xl border p-3 {tone.card}">
							<Tip text={kind.keyword} slow align="start">
								<span class="grid size-9 shrink-0 place-items-center rounded-lg {tone.box}">
									<Icon name={kind.icon} />
								</span>
							</Tip>
							<p class="text-sm">
								{#if kind.remark}<strong class={tone.remark}>{kind.remark}</strong>{/if}
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
			<h2 class="text-lg font-semibold">{m.grades_subjects()}</h2>
			<p class="text-xs text-muted">{m.grades_subjects_hint()}</p>
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
								{#if s.growth}
									<span
										class="rounded-full bg-surface px-2 py-0.5 text-[11px] font-medium text-navy"
										title={m.grades_growth_title()}
										>{GROWTH[s.growth.label].sign} {GROWTH[s.growth.label].label}</span
									>
								{/if}
							</div>
							<p class="mt-0.5 text-xs text-subtle">
								{s.class_name} · {s.n_marks === 1 ? m.grades_n_mark({ n: s.n_marks }) : m.grades_n_marks({ n: s.n_marks })}
								{#if s.class_comparison}
									· {m.grades_vs_class({ delta: fmtSigned(s.class_comparison.delta) })}
								{/if}
								{#if s.attendance}
									· {m.grades_absent({ rate: pct(s.attendance.rate) })}
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
								<div class="text-[11px] text-subtle">{m.grades_rounds_to()} {s.current.rounded}</div>
							{/if}
						</div>
						<span class="text-muted transition {open === i ? '-rotate-90' : 'rotate-180'}">
							<Icon name="back" />
						</span>
					</button>
					
					{#if open === i}
						{@const fail = s.forecast?.fail_probability}
						<div class="border-t border-divider p-4 sm:p-5">
							{#if s.required_remaining_avg != null || fail != null}
								<div class="mb-5 space-y-2">
									{#if s.required_remaining_avg != null}
										<!-- Handlungsspielraum statt Urteil -->
										<p
											class="rounded-xl px-4 py-3 text-sm {!s.reachable
												? 'bg-error/10 text-error'
												: s.secured
													? 'bg-success/12 text-success-dark'
													: 'bg-accent-light text-accent-dark'}"
										>
											{#if !s.reachable}
												{m.grades_unreachable()}
											{:else if s.secured}
												{m.grades_secured()}
											{:else}
												{m.notice_need_before()} <strong>{fmtGrade(s.required_remaining_avg)}</strong>
												{m.grades_need_after_subject()}
											{/if}
										</p>
									{/if}
									{#if fail != null}
										<!-- nur Lehrkräfte/Admin: die API liefert das Feld Schülern nicht -->
										<div
											class="flex items-center gap-3 rounded-xl px-4 py-3 text-sm {failTone(fail)}"
										>
											<span class="font-heading text-xl font-bold tabular-nums">{pct(fail, 0)}</span
											>
											<span class="flex-1">
												{m.grades_fail_chance()}
												<span class="block text-xs opacity-80"
													>{m.grades_model_estimate()}</span
												>
											</span>
											<Tip
												align="end"
												text={m.grades_fail_tip({ pass: passMark, version: s.forecast.model_version })}
											/>
										</div>
									{/if}
								</div>
							{/if}

							{#if s.possible && s.possible.low !== s.possible.high}
								{@const likely = s.forecast?.likely}
								<!-- Hell: noch möglich (Regeln, live). Dunkel: wahrscheinlich (Prognosemodell, 80 %) -->
								<div class="mb-6">
									<h4
										class="mb-2 flex items-center gap-1.5 text-xs font-medium tracking-wide text-subtle uppercase"
									>
										{likely ? m.grades_heading() : m.grades_still_possible()}
										<Tip
											align="start"
											text={likely
												? `${m.grades_likely_tip()}${s.forecast.computed_at ? ` ${m.grades_updated({ when: when(s.forecast.computed_at) })}` : ''}`
												: m.grades_possible_tip()}
										/>
									</h4>
									<RangeBar
										low={s.possible.low}
										high={s.possible.high}
										current={s.current.raw}
										likelyLow={likely?.low}
										likelyHigh={likely?.high}
										{passMark}
									/>
								</div>
							{/if}

							<div class="grid gap-6 lg:grid-cols-2">
								<div>
									<h4 class="mb-3 text-xs font-medium tracking-wide text-subtle uppercase">
										{m.grades_made_up()}
									</h4>
									<ComponentBars components={s.components} />
								</div>
								<div>
									<h4
										class="mb-1 flex items-center gap-1.5 text-xs font-medium tracking-wide text-subtle uppercase"
									>
										{m.grades_over_year()}
										<Tip
											align="start"
											text={m.grades_over_year_tip()}
										/>
									</h4>
									<GradeTimeline
										progression={s.progression ?? []}
										marks={s.marks ?? []}
										trimesters={stats.trimesters ?? []}
										today={stats.as_of}
										{passMark}
									/>
								</div>
							</div>

							<div class="mt-6 grid gap-6 lg:grid-cols-2">
								{#if s.attendance}
									<div>
										<h4 class="mb-3 text-xs font-medium tracking-wide text-subtle uppercase">
											{m.nav_attendance()}
										</h4>
										<AbsenceBudget absence={s.attendance} />
									</div>
								{/if}
								{#if s.recent.length}
									<div>
										<h4 class="mb-2 text-xs font-medium tracking-wide text-subtle uppercase">
											{m.grades_latest()}
										</h4>
										<ul class="divide-y divide-divider text-sm">
											{#each s.recent as r}
												<li class="flex items-center justify-between py-2">
													<span>
														{categoryLabel(r.category)}
														<span class="ml-1.5 text-[11px] text-muted">
															{r.component}{r.weight !== 1 ? ` · ${m.grades_weight({ w: r.weight })}` : ''}
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
									</div>
								{/if}
							</div>
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
			{m.grades_how_work()}
			<span class="text-muted transition {rulesOpen ? '-rotate-90' : 'rotate-180'}"
				><Icon name="back" /></span
			>
		</summary>
		<ul class="space-y-2 border-t border-divider p-5 text-sm text-subtle">
			<li>{m.rule1_before()} <strong class="text-navy">{m.rule1_range()}</strong>{m.rule1_after()}</li>
			<li>
				{m.rule2_before()} <strong class="text-navy">{passMark}</strong>{m.rule2_after()}
			</li>
			<li>
				{m.rule3_before()} <strong class="text-navy">40 % Mitarbeit</strong>,
				<strong class="text-navy">40 % Schularbeit</strong>
				{m.rule3_and()} <strong class="text-navy">20 % Projekt</strong>{m.rule3_after()}
			</li>
			<li>{m.rule4()}</li>
			<li>{m.rule5()}</li>
			<li>{m.rule6({ value: stats.scale.fragile_below })}</li>
			<li>{m.rule7()}</li>
		</ul>
	</details>
{/if}