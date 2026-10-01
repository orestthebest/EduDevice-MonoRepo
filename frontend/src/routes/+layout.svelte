<script>
	// Globales Stylesheet (Tailwind + Corporate Design) einbinden.
	import './layout.css';

	// children = der Inhalt der jeweiligen Seite
	let { children } = $props();
</script>

<svelte:head>
	<title>EduDevice</title>
</svelte:head>

{@render children()}