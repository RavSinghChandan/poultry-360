import { Routes } from '@angular/router';

/**
 * One route per feature, matching the backend's feature key.
 *
 * Adding a feature means adding one lazy route here and one component folder.
 * Nothing else in the shell changes — the menu builds itself from
 * /api/features.
 */
export const routes: Routes = [
  { path: '', redirectTo: 'count', pathMatch: 'full' },
  {
    path: 'feed',
    loadComponent: () =>
      import('./features/feed/feed.component').then((m) => m.FeedComponent),
  },
  {
    path: 'health',
    loadComponent: () =>
      import('./features/health/health.component').then((m) => m.HealthComponent),
  },
  {
    path: 'count',
    loadComponent: () =>
      import('./features/count/count.component').then((m) => m.CountComponent),
  },
  { path: '**', redirectTo: 'count' },
];
