<script>
	import AuthLayout from '$lib/components/AuthLayout.svelte';

	// form enthält eine Fehlermeldung vom Login-Action.
	let { form } = $props();
</script>

<svelte:head>
	<title>Log in · EduDevice</title>
</svelte:head>

<AuthLayout>
	<h1 class="text-center text-4xl font-bold">Log in</h1>
	<p class="mt-2 text-center text-muted">Welcome back! Log in with your school account.</p>

	<!-- Fehlermeldung anzeigen, falls der Login fehlgeschlagen ist -->
	{#if form?.error}
		<p class="mt-6 rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
			{form.error}
		</p>
	{/if}

	<!-- Login-Formular: schickt Username + Passwort an den login-Action -->
	<form action="?/login" method="POST" class="mt-8 flex flex-col gap-6">
		<div>
			<label for="username" class="label">Username</label>
			<input
				type="text"
				id="username"
				name="username"
				required
				placeholder="e.g. elira.krasniqi"
				autocomplete="username"
				value={form?.username ?? ''}
				class="input"
			/>
		</div>

		<div>
			<label for="password" class="label">Password</label>
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

		<button type="submit" class="btn-primary">Log in</button>

		<!-- Link zur Registrierung für User ohne Account -->
		<p class="text-center text-sm text-muted">
			No account?
			<a href="/register" class="font-medium text-accent hover:underline">Register here</a>
		</p>
	</form>
</AuthLayout>