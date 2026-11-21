// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// FORGE documentation. Pages live in src/content/docs/; images in src/assets/.
// https://starlight.astro.build/reference/configuration/
export default defineConfig({
	integrations: [
		starlight({
			title: 'FORGE',
			description: 'From a thought to a game-ready 3D asset, on your own AMD PC.',
			logo: { src: './src/assets/icon.png' },
			favicon: '/favicon.png',
			social: [{ icon: 'github', label: 'GitHub', href: 'https://github.com/Caraveo/forge' }],
			editLink: { baseUrl: 'https://github.com/Caraveo/forge/edit/main/docs-site/' },
			lastUpdated: true,
			customCss: ['./src/styles/forge.css'],
			sidebar: [
				{ label: 'Welcome', link: '/' },
				{
					label: 'Getting started',
					items: [
						'getting-started/requirements',
						'getting-started/install',
						'getting-started/first-model',
					],
				},
				{
					label: 'Using FORGE',
					items: [
						'using-forge/commands-and-chat',
						'using-forge/projects-and-jobs',
						'using-forge/quality',
						'using-forge/attachments',
						'using-forge/results-and-files',
						'using-forge/rigging',
						'using-forge/command-line',
					],
				},
				{
					label: 'Important',
					items: [
						'important/before-you-install',
						'important/privacy-and-downloads',
						'important/licenses',
					],
				},
				{
					label: 'Troubleshooting',
					items: ['troubleshooting/common-problems', 'troubleshooting/logs'],
				},
				{
					label: 'Reference',
					items: [
						'reference/changelog',
						'reference/keyboard-and-mouse',
						'reference/uninstall',
						'reference/build-from-source',
					],
				},
			],
		}),
	],
});
