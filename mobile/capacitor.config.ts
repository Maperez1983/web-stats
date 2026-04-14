import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "es.segundajugada.app",
  appName: "2J Football Intelligence",
  webDir: "www",
  // Wrapper tipo “app real”: carga la web remota y usa plugins nativos.
  server: {
    url: "https://app.segundajugada.es",
    cleartext: false,
  },
  plugins: {
    SplashScreen: {
      // Evita que se auto-oculte “por timeout” antes de que cargue la web remota.
      // La ocultamos nosotros al terminar de cargar (ver MainViewController en iOS).
      launchShowDuration: 30000,
      launchAutoHide: false,
    },
  },
  ios: {
    contentInset: "automatic",
  },
};

export default config;
