# OF Backup Exporter para Chrome

Esta variante usa el mismo flujo local y el mismo formato
`OFBackup-auth.json` que la extensión de Firefox.

Para generar el directorio instalable y el ZIP:

```bash
npm run build:chrome
```

Después puedes probarla en Chrome PC:

1. Abre `chrome://extensions`.
2. Activa **Modo de desarrollador**.
3. Pulsa **Cargar descomprimida**.
4. Elige la carpeta `build/chrome`.

La extensión solo solicita acceso a OnlyFans, cookies, la pestaña activa y
descargas. No transmite ni almacena credenciales fuera del archivo local que
solicita el usuario.
