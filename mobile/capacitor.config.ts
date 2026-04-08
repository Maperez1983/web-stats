import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "es.segundajugada.app",
  appName: "SegundaJugada",
  webDir: "www",
  // Wrapper tipo “app real”: carga la web remota y usa plugins nativos.
  server: {
    url: "https://app.segundajugada.es",
    cleartext: false,
  },
  ios: {
    contentInset: "automatic",
  },
};

export default config;

