<script>
	import AuthLayout from '$lib/components/AuthLayout.svelte';
	import { m } from '$lib/paraglide/messages.js';

	// form enthält eine Fehlermeldung vom Login-Action.
	let { form } = $props();
	// Ausgewählte Rolle (Student ist Standard)
	let role = $state('student');

	const roles = [
		{ value: 'student', label: m.role_student() },
		{ value: 'teacher', label: m.role_teacher() },
		{ value: 'admin', label: m.role_admin() }
	];
</script>

<svelte:head>
	<title>{m.login_title()} · EduDevice</title>
</svelte:head>

<AuthLayout>
	<h1 class="text-center text-4xl font-bold">{m.login_title()}</h1>
	<p class="mt-2 text-center text-subtle">{m.login_subtitle()}</p>

	<!-- Fehlermeldung anzeigen, falls der Login fehlgeschlagen ist -->
	{#if form?.error}
		<p class="mt-6 rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
			{form.error}
		</p>
	{/if}

	<!-- Login-Formular: schickt Username + Passwort an den login-Action -->
	<form action="?/login" method="POST" class="mt-8 flex flex-col gap-6">
		<div>
			<label for="username" class="label">{m.username()}</label>
			<input
				type="text"
				id="username"
				name="username"
				required
				placeholder={m.username_placeholder()}
				autocomplete="username"
				value={form?.username ?? ''}
				class="input"
			/>
		</div>

		<div>
			<label for="password" class="label">{m.password()}</label>
			<input
				type="password"
				id="password"
				name="password"
				required
				placeholder="••••••••"
				autocomplete="current-password"
				class="input"
			/>
		</div>

		<!-- Rollen-Auswahl: wird beim Login mit der Rolle in der DB verglichen -->
		<fieldset>
			<legend class="label">{m.login_sign_in_as()}</legend>
			<div class="grid grid-cols-3 gap-3">
				{#each roles as r (r.value)}
					<label
						class="cursor-pointer rounded-lg border py-2.5 text-center text-sm font-medium transition
						{role === r.value
							? 'border-accent bg-accent-xlight text-accent-dark'
							: 'border-ghost bg-white text-navy hover:border-accent/50'}"
					>
						<input type="radio" name="role" value={r.value} bind:group={role} class="sr-only" />
						{r.label}
					</label>
				{/each}
			</div>
		</fieldset>
		<button type="submit" class="btn-primary">{m.login_button()}</button>

		<!-- Link zur Registrierung für User ohne Account -->
		<p class="text-center text-sm text-subtle">
			{m.login_no_account()}
			<a href="/register" class="font-medium text-accent hover:text-accent-darker">{m.login_register_link()}</a>
		</p>
	</form>
</AuthLayout>