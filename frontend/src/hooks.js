import { deLocalizeUrl } from '$lib/paraglide/runtime.js';

/** @type {import('@sveltejs/kit').Reroute} */ export const reroute = (request) =>
	deLocalizeUrl(request.url).pathname;
