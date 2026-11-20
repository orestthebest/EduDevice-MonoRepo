<script>
	// Kurzer Hinweis beim Darüberfahren, Antippen oder mit Tab.
	//
	// Ohne Inhalt: ein kleines "i". Mit Inhalt (z. B. einem Icon): der Inhalt
	// löst den Hinweis aus. slow = erst nach einer kurzen Pause, für Icons, die
	// man beim Lesen nur streift. align: wo der Hinweis am Auslöser ansetzt
	// (start / center / end), damit er am Rand der Karte nicht abgeschnitten wird.
	let { text, slow = false, align = 'center', children } = $props();
	const id = $props.id();
	const place = { start: 'left-0', center: 'left-1/2 -translate-x-1/2', end: 'right-0' };
</script>

<span class="group relative inline-flex align-middle">
	{#if children}
		<span
			tabindex="0"
			role="button"
			aria-describedby={id}
			class="inline-flex rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-accent"
		>
			{@render children()}
		</span>
	{:else}
		<button
			type="button"
			aria-label="More information"
			aria-describedby={id}
			class="grid size-4 cursor-help place-items-center rounded-full border border-current text-[10px] leading-none font-semibold text-muted normal-case hover:text-navy focus-visible:text-navy"
			>i</button
		>
	{/if}
	<span
		{id}
		role="tooltip"
		class="pointer-events-none absolute bottom-full z-20 mb-2 w-max max-w-64 rounded-lg bg-navy px-3 py-2 text-xs font-normal tracking-normal text-white normal-case opacity-0 shadow-lg transition-opacity group-focus-within:opacity-100 group-hover:opacity-100 {slow
			? 'group-hover:delay-500'
			: ''} {place[align]}"
	>
		{text}
	</span>
</span>