import { APP_INITIALIZER, ApplicationConfig } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { routes } from './app.routes';
import { authInterceptor } from './core/auth.service';
import { I18nService } from './core/i18n.service';

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(withInterceptors([authInterceptor])),
    // words load before the first screen, so nobody sees raw keys
    { provide: APP_INITIALIZER, multi: true, deps: [I18nService], useFactory: (i18n: I18nService) => () => i18n.init() },
  ],
};
