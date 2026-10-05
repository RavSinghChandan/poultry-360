import { Routes } from '@angular/router';
import { signedIn } from './core/auth.service';

/**
 * One route per feature, matching the backend's feature key.
 *
 * Adding a feature means adding one lazy route here and one component folder.
 * Nothing else in the shell changes — the menu builds itself from
 * /api/features. Feature pages need a signed-in farm when the server asks for it.
 */
export const routes: Routes = [
  { path: '', redirectTo: 'count', pathMatch: 'full' },
  { path: 'welcome', loadComponent: () => import('./pages/home.page').then((m) => m.HomePage) },
  { path: 'login', loadComponent: () => import('./pages/login.page').then((m) => m.LoginPage) },
  { path: 'register', loadComponent: () => import('./pages/register.page').then((m) => m.RegisterPage) },
  { path: 'admin', loadComponent: () => import('./pages/admin.page').then((m) => m.AdminPage) },
  {
    path: 'feed',
    canActivate: [signedIn],
    loadComponent: () =>
      import('./features/feed/feed.component').then((m) => m.FeedComponent),
  },
  {
    path: 'health',
    canActivate: [signedIn],
    loadComponent: () =>
      import('./features/health/health.component').then((m) => m.HealthComponent),
  },
  {
    path: 'count',
    canActivate: [signedIn],
    loadComponent: () =>
      import('./features/count/count.component').then((m) => m.CountComponent),
  },
  { path: '**', redirectTo: 'count' },
];
