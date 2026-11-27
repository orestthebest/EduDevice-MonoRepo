<script>
	import { enhance } from '$app/forms';
	import Icon from '$lib/components/Icon.svelte';
	import { formatSize } from '$lib/format.js';
	import { m } from '$lib/paraglide/messages.js';

	// Anhänge einer Entschuldigung: Name öffnet im neuen Tab, Pfeil lädt herunter, ✕ entfernt (nur Schüler, nur pending)
	let { excuseId, attachments = [], canRemove = false } = $props();
	let removingId = $state(null);

	// Vorschau im Dialog (PDF + Bilder); andere Dateitypen öffnen weiter im neuen Tab
	let previewDialog = $state();
	let preview = $state(null); // { name, href, kind }
	const kindOf = (name) => (/\.pdf$/i.test(name) ? 'pdf' : /\.(jpe?g|png)$/i.test(name) ? 'image' : null);

	function openPreview(att, href) {
		preview = { name: att.original_name, href, kind: kindOf(att.original_name) };
		previewDialog.showModal();
	}
</script>

{#if attachments.length > 0}
	<ul class="mt-2 flex flex-wrap gap-2">
		{#each attachments as att (att.id)}
			{@const href = `/excuses/${excuseId}/attachments/${att.id}`}
			<li class="flex max-w-full items-center gap-1 rounded-lg border border-line bg-surface py-1 pr-1 pl-3 text-sm">
				<Icon name="file" class="size-4 shrink-0 text-subtle" />
				{#if kindOf(att.original_name)}
					<button type="button" onclick={() => openPreview(att, href)} title={m.exc_preview({ name: att.original_name })}
						class="min-w-0 cursor-pointer truncate font-medium hover:text-accent-dark hover:underline">{att.original_name}</button>
				{:else}
					<a href="{href}?view" target="_blank" rel="noopener"
						class="min-w-0 truncate font-medium hover:text-accent-dark hover:underline">{att.original_name}</a>
				{/if}
				<span class="shrink-0 pl-1 text-xs text-subtle">{formatSize(att.size_bytes)}</span>
				<a {href} download aria-label={m.download_item({ name: att.original_name })}
					class="rounded-md p-1 text-subtle transition hover:bg-white hover:text-accent-dark">
					<Icon name="download" class="size-4" />
				</a>
				{#if canRemove}
					<form method="POST" action="?/removeAttachment"
						use:enhance={() => {
							removingId = att.id;
							return async ({ update }) => {
								await update();
								removingId = null;
							};
						}}>
						<input type="hidden" name="excuse_id" value={excuseId} />
						<input type="hidden" name="attachment_id" value={att.id} />
						<button type="submit" disabled={removingId === att.id} aria-label={m.remove_item({ name: att.original_name })}
							class="cursor-pointer rounded-md p-1 text-subtle transition hover:bg-white hover:text-error disabled:opacity-50">
							<Icon name="x" class="size-4" />
						</button>
					</form>
				{/if}
			</li>
		{/each}
	</ul>
{/if}

<!-- Vorschau-Dialog: Klick auf den Hintergrund oder Esc schließt -->
<dialog bind:this={previewDialog} onclose={() => (preview = null)}
	onclick={(e) => e.target === previewDialog && previewDialog.close()}
	class="m-auto h-[85vh] w-[min(56rem,95vw)] max-w-none rounded-2xl border border-line bg-white p-0 text-navy shadow-xl backdrop:bg-navy/35">
	{#if preview}
		<div class="flex h-full flex-col">
			<div class="flex items-center gap-1 border-b border-line py-2 pr-2 pl-4">
				<span class="min-w-0 flex-1 truncate text-sm font-semibold">{preview.name}</span>
				<a href={preview.href} download aria-label={m.download_item({ name: preview.name })}
					class="rounded-md p-1.5 text-subtle transition hover:bg-surface hover:text-accent-dark">
					<Icon name="download" class="size-4" />
				</a>
				<button type="button" onclick={() => previewDialog.close()} aria-label={m.close()}
					class="cursor-pointer rounded-md p-1.5 text-subtle transition hover:bg-surface hover:text-navy">
					<Icon name="x" class="size-4" />
				</button>
			</div>
			<div class="min-h-0 flex-1 bg-surface">
				{#if preview.kind === 'image'}
					<img src="{preview.href}?view" alt={preview.name} class="size-full object-contain p-4" />
				{:else}
					<iframe src="{preview.href}?view" title={preview.name} class="size-full"></iframe>
				{/if}
			</div>
		</div>
	{/if}
</dialog>