<script>
	// data.user kommt aus +layout.server.js
	let { data } = $props();

	// Rollen aus der Datenbank (Deutsch) für die Anzeige übersetzen
	const roleLabels = { schueler: 'Student', lehrkraft: 'Teacher', admin: 'Admin' };
</script>

<main class="flex min-h-screen items-center justify-center bg-surface p-6">
	<div class="w-full max-w-md rounded-2xl bg-white p-8 shadow-sm">
		<img src="/logo.png" alt="EduDevice" class="mb-8 h-10 w-auto" />
		<h1 class="text-2xl font-bold">Welcome, {data.user.first_name}!</h1>
		<p class="mt-2 text-muted">{data.user.email} · {roleLabels[data.user.role]}</p>

		<form action="/logout?/logout" method="POST" class="mt-8">
			<button type="submit" class="btn-primary">Log out</button>
		</form>
	</div>
</main>