<script>
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { locales, localizeHref } from '$lib/paraglide/runtime.js';

	// Globales Stylesheet (Tailwind + Corporate Design) einbinden.
	import './layout.css';

	// children = der Inhalt der jeweiligen Seite
	let { children } = $props();
</script>

<svelte:head>
	<title>EduDevice</title>
</svelte:head>

{@render children()}

<div style="display:none">
	{#each locales as locale (locale)}
		<a href={resolve(localizeHref(page.url.pathname, { locale }))}>{locale}</a>
	{/each}
</div>
