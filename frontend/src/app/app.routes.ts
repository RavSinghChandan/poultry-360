import { CanActivateFn, Router, Routes } from '@angular/router';
import { inject } from '@angular/core';
import { signedIn } from './core/auth.service';
import { I18nService } from './core/i18n.service';

/** First visit: pick a language before anything else, then come back. */
const languageChosen: CanActivateFn = (_r, state) =>
  inject(I18nService).chosen() || inject(Router).createUrlTree(['/language'], { queryParams: { next: state.url } });

/**
 * The app opens on Today: the flock at a glance and one big button per job.
 * Every tool page needs a signed-in farm when the server asks for it.
 */
export const routes: Routes = [
  { path: '', redirectTo: 'today', pathMatch: 'full' },
  { path: 'language', loadComponent: () => import('./pages/language.page').then((m) => m.LanguagePage) },
  { path: 'welcome', canActivate: [languageChosen], loadComponent: () => import('./pages/home.page').then((m) => m.HomePage) },
  { path: 'login', loadComponent: () => import('./pages/login.page').then((m) => m.LoginPage) },
  { path: 'register', canActivate: [languageChosen], loadComponent: () => import('./pages/register.page').then((m) => m.RegisterPage) },
  { path: 'admin', loadComponent: () => import('./pages/admin.page').then((m) => m.AdminPage) },
  { path: 'today', canActivate: [languageChosen, signedIn], loadComponent: () => import('./pages/today.page').then((m) => m.TodayPage) },
  { path: 'diary', canActivate: [languageChosen, signedIn], loadComponent: () => import('./pages/diary.page').then((m) => m.DiaryPage) },
  { path: 'feed', canActivate: [languageChosen, signedIn], loadComponent: () => import('./features/feed/feed.component').then((m) => m.FeedComponent) },
  { path: 'health', canActivate: [languageChosen, signedIn], loadComponent: () => import('./features/health/health.component').then((m) => m.HealthComponent) },
  { path: 'count', canActivate: [languageChosen, signedIn], loadComponent: () => import('./features/count/count.component').then((m) => m.CountComponent) },
  { path: '**', redirectTo: 'today' },
];
