<script>
	import { enhance } from '$app/forms';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { ROLE_LABEL } from '$lib/roles.js';
    import Avatar from '$lib/components/Avatar.svelte';
    import Icon from '$lib/components/Icon.svelte';
	import { m } from '$lib/paraglide/messages.js';

	let { data, form } = $props();
    let saving = $state(false);
    let savingUsername = $state(false);
	let savingPassword = $state(false);
    let uploading = $state(false);
	const p = $derived(data.profile);
</script>

<svelte:head>
	<title>{m.nav_profile()} · EduDevice</title>
</svelte:head>

<PageHeader title={m.prof_title()} subtitle={m.prof_subtitle()} />

<!-- Kopf-Karte: Bild/Initialen, Name, Rolle, Bild ändern -->
<section class="rounded-xl border border-line bg-white p-4 sm:p-5">
	<div class="flex flex-col gap-4 sm:flex-row sm:items-center">
		<Avatar user={p} class="size-16 text-xl" />

		<div class="min-w-0 flex-1">
			<h2 class="truncate text-lg font-semibold">{p.first_name} {p.last_name}</h2>
			<p class="truncate text-sm text-subtle">@{p.username}</p>
			<span class="mt-1 inline-block rounded-md bg-accent-light px-2 py-0.5 text-xs font-semibold text-accent-dark">
				{ROLE_LABEL[p.role]}
			</span>
		</div>

		<div class="flex gap-2">
			<!-- Datei wählen -> Formular schickt sich sofort ab -->
			<form method="POST" action="?/uploadAvatar" enctype="multipart/form-data"
				use:enhance={() => {
					uploading = true;
					return async ({ update }) => {
						await update();
						uploading = false;
					};
				}}
			>
				<label class="flex cursor-pointer items-center gap-2 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white transition hover:bg-accent-dark">
					<Icon name="upload" />
					{uploading ? m.prof_uploading() : p.profile_image ? m.prof_change_picture() : m.prof_upload_picture()}
					<input type="file" name="file" accept="image/jpeg,image/png,image/webp" class="hidden"
						disabled={uploading} onchange={(e) => e.currentTarget.form.requestSubmit()} />
				</label>
			</form>

			{#if p.profile_image}
				<form method="POST" action="?/removeAvatar" use:enhance>
					<button type="submit"
						class="flex cursor-pointer items-center gap-2 rounded-lg border border-ghost px-3 py-1.5 text-sm font-medium transition hover:border-error hover:text-error">
						<Icon name="trash" />
						{m.prof_remove()}
					</button>
				</form>
			{/if}
		</div>
	</div>

	<!-- Name und Rolle verwaltet die Schule, daher hier nur der Hinweis statt einer eigenen Karte -->
	<p class="mt-3 text-xs text-subtle">{m.prof_image_hint()} · {m.prof_account_hint()}</p>

	{#if form?.avatarError}
		<p class="mt-3 rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">{form.avatarError}</p>
	{:else if form?.avatarSuccess}
		<p class="mt-3 rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-sm text-success-dark">{form.avatarSuccess}</p>
	{/if}
</section>


<!-- Benutzername, E-Mail, Passwort: eine Karte, je Zeile Titel links und Formular rechts -->
<section class="mt-4 divide-y divide-divider rounded-xl border border-line bg-white px-4 sm:px-5">
	<div class="grid gap-3 py-4 sm:grid-cols-[12rem_minmax(0,1fr)] sm:gap-6">
		<div>
			<h2 class="text-sm font-semibold">{m.username()}</h2>
			<p class="text-xs text-subtle">{m.prof_username_hint()}</p>
		</div>
		<div>
			<form
				method="POST"
				action="?/updateUsername"
				class="flex flex-col gap-3 sm:flex-row sm:items-end"
				use:enhance={() => {
					savingUsername = true;
					return async ({ update }) => {
						await update({ reset: false });
						savingUsername = false;
					};
				}}
			>
				<div class="flex-1">
					<label for="username" class="sr-only">{m.username()}</label>
					<input id="username" name="username" type="text" required minlength="3" maxlength="50"
						autocomplete="username" class="input" value={form?.username ?? p.username} />
				</div>
				<button type="submit" class="btn-primary sm:w-auto sm:px-5" disabled={savingUsername}>
					{savingUsername ? m.saving() : m.save()}
				</button>
			</form>

			{#if form?.usernameError}
				<p class="mt-3 rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">{form.usernameError}</p>
			{:else if form?.usernameSuccess}
				<p class="mt-3 rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-sm text-success-dark">{m.prof_username_updated()}</p>
			{/if}
		</div>
	</div>
	<div class="grid gap-3 py-4 sm:grid-cols-[12rem_minmax(0,1fr)] sm:gap-6">
		<div>
			<h2 class="text-sm font-semibold">{m.prof_email_title()}</h2>
			<p class="text-xs text-subtle">{m.prof_email_hint()}</p>
		</div>
		<div>
			<form
				method="POST"
				action="?/updateEmail"
				class="flex flex-col gap-3 sm:flex-row sm:items-end"
				use:enhance={() => {
					saving = true;
					return async ({ update }) => {
						await update({ reset: false });
						saving = false;
					};
				}}
			>
				<div class="flex-1">
					<label for="email" class="sr-only">{m.email()}</label>
					<input id="email" name="email" type="email" required maxlength="255"
						class="input" value={form?.email ?? p.email} />
				</div>
				<button type="submit" class="btn-primary sm:w-auto sm:px-5" disabled={saving}>
					{saving ? m.saving() : m.save()}
				</button>
			</form>

			{#if form?.error}
				<p class="mt-3 rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">{form.error}</p>
			{:else if form?.success}
				<p class="mt-3 rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-sm text-success-dark">{m.prof_email_updated()}</p>
			{/if}
		</div>
	</div>
	<div class="grid gap-3 py-4 sm:grid-cols-[12rem_minmax(0,1fr)] sm:gap-6">
		<div>
			<h2 class="text-sm font-semibold">{m.password()}</h2>
			<p class="text-xs text-subtle">{m.prof_password_hint()}</p>
		</div>
		<div>
			<form
				method="POST"
				action="?/updatePassword"
				class="grid gap-3 sm:grid-cols-3"
				use:enhance={() => {
					savingPassword = true;
					return async ({ update }) => {
						await update(); // leert die Felder nach Erfolg
						savingPassword = false;
					};
				}}
			>
				<div>
					<label for="current_password" class="label">{m.prof_current_password()}</label>
					<input id="current_password" name="current_password" type="password" required
						autocomplete="current-password" class="input" />
				</div>
				<div>
					<label for="new_password" class="label">{m.prof_new_password()}</label>
					<input id="new_password" name="new_password" type="password" required minlength="8" maxlength="72"
						autocomplete="new-password" class="input" />
				</div>
				<div>
					<label for="confirm_password" class="label">{m.prof_repeat_password()}</label>
					<input id="confirm_password" name="confirm_password" type="password" required minlength="8" maxlength="72"
						autocomplete="new-password" class="input" />
				</div>
				<div class="sm:col-span-3 sm:flex sm:justify-end">
					<button type="submit" class="btn-primary sm:w-auto sm:px-5" disabled={savingPassword}>
						{savingPassword ? m.saving() : m.prof_change_password()}
					</button>
				</div>
			</form>

			{#if form?.passwordError}
				<p class="mt-3 rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">{form.passwordError}</p>
			{:else if form?.passwordSuccess}
				<p class="mt-3 rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-sm text-success-dark">{m.prof_password_changed()}</p>
			{/if}
		</div>
	</div>
</section>