<script>
	// Kleine Icon-Sammlung (Lucide-Stil, inline SVG)
	let { name, class: cls = 'size-4' } = $props();

	const paths = {
		home: 'M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z',
		book: 'M2 4h6a4 4 0 0 1 4 4v13a3 3 0 0 0-3-3H2zM22 4h-6a4 4 0 0 0-4 4v13a3 3 0 0 1 3-3h7z',
		folder: 'M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',
		grid: 'M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z',
		file: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5',
		logout: 'M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9',
		menu: 'M4 6h16M4 12h16M4 18h16',
		x: 'M18 6 6 18M6 6l12 12',
		arrow: 'M5 12h14M13 6l6 6-6 6',
		upload: 'M12 16V4M7 9l5-5 5 5M4 20h16',
		download: 'M12 4v12M7 11l5 5 5-5M4 20h16',
		trash: 'M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3',
		plus: 'M12 5v14M5 12h14',
		back: 'M15 6l-6 6 6 6'
	};
</script>

<svg class={cls} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
	stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
	<path d={paths[name]} />
</svg>