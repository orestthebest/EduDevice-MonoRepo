<script>
	import { m } from '$lib/paraglide/messages.js';
	import { locales, getLocale, setLocale } from '$lib/paraglide/runtime.js';

	// class = zusätzliche Klassen von außen (z.B. Abstand, Hintergrund)
	let { class: className = '' } = $props();
</script>

<!-- Sprachauswahl: setLocale speichert die Sprache im Cookie und lädt die Seite neu -->
<div class="flex gap-1 rounded-lg border border-ghost p-1 {className}" role="group" aria-label={m.language()}>
	{#each locales as locale (locale)}
		<button
			type="button"
			onclick={() => setLocale(locale)}
			class="rounded-md px-2.5 py-1 text-xs font-semibold uppercase transition
			{getLocale() === locale ? 'bg-accent-xlight text-accent-dark' : 'text-subtle hover:text-navy'}"
		>
			{locale}
		</button>
	{/each}
</div>