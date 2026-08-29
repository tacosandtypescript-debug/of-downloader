# OF Downloader Companion para Android

Este módulo es un prototipo de aplicación Android. El login ocurre en un
WebView creado por la aplicación y el usuario debe pulsar **Generar archivo**
para iniciar una exportación explícita.

La aplicación:

- solo permite navegación dentro de `onlyfans.com` y sus subdominios;
- permite elegir una cuenta Google del dispositivo para rellenar solo el correo;
- lee únicamente las cookies de su propio WebView;
- genera el formato `ofbackup-auth` que entiende OF Downloader;
- usa el selector de documentos de Android, sin permisos de almacenamiento;
- permite borrar las cookies de esa aplicación.

No intenta acceder a las cookies almacenadas por Chrome, Firefox u otras
aplicaciones.

El selector de cuentas solo proporciona la dirección de correo. La contraseña
se introduce en el formulario de OnlyFans, o se puede pulsar su botón oficial
**Sign in with Google** cuando el sitio lo ofrezca.

## Compilar

Desde `android/`:

```bash
cd android
gradle assembleDebug
```

El APK resultante queda en:

```text
android/build/outputs/apk/debug/android-debug.apk
```
