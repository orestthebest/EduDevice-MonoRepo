import { m } from '$lib/paraglide/messages.js';

// Rollen aus der DB (users.role) -> Anzeigename.
// Getter: der Text wird erst beim Zugriff in der aktuellen Sprache geholt.
export const ROLE_LABEL = {
	get schueler() { return m.role_student(); },
	get lehrkraft() { return m.role_teacher(); },
	get admin() { return m.role_admin(); }
};

// Sidebar-Navigation. section und label sind Funktionen -> im Layout mit () aufrufen.
export const NAV = {
	schueler: {
		section: m.nav_section_learning,
		items: [
			{ href: '/', label: m.nav_dashboard, icon: 'home' },
			{ href: '/grades', label: m.nav_my_grades, icon: 'grid' },
			{ href: '/subjects', label: m.nav_subjects_materials, icon: 'book' },
			{ href: '/excuses', label: m.nav_excuses, icon: 'clipboard' },
			{ href: '/timetable', label: m.nav_timetable, icon: 'clock' }
		]
	},
	lehrkraft: {
		section: m.nav_section_teaching,
		items: [
			{ href: '/', label: m.nav_dashboard, icon: 'home' },
			{ href: '/subjects', label: m.nav_subjects_materials, icon: 'folder' },
			{ href: '/excuses/review', label: m.nav_excuse_review, icon: 'clipboard' },
			{ href: '/attendance', label: m.nav_attendance, icon: 'calendar' },
			{ href: '/timetable', label: m.nav_timetable, icon: 'clock' }
		]
	},
	admin: {
		section: m.nav_section_admin,
		items: [
			{ href: '/', label: m.nav_dashboard, icon: 'home' },
			{ href: '/classes', label: m.nav_classes_students, icon: 'users' },
			{ href: '/subjects', label: m.nav_all_subjects, icon: 'grid' },
			{ href: '/excuses/review', label: m.nav_excuse_review, icon: 'clipboard' },
			{ href: '/timetable/manage', label: m.nav_timetables, icon: 'clock' }
		]
	}
};

// Für alle Rollen gleich (wie im Wireframe unter "Shared")
export const SHARED_NAV = {
	section: m.nav_section_shared,
	items: [{ href: '/profile', label: m.nav_profile, icon: 'user' }]
};