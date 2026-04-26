import UIKit
import Capacitor
import WebKit
import Security

@UIApplicationMain
class AppDelegate: UIResponder, UIApplicationDelegate {

    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        // Override point for customization after application launch.
        return true
    }

    // iOS 13+: Scene lifecycle (requerido por versiones futuras de iOS).
    func application(_ application: UIApplication, configurationForConnecting connectingSceneSession: UISceneSession, options: UIScene.ConnectionOptions) -> UISceneConfiguration {
        return UISceneConfiguration(name: "Default Configuration", sessionRole: connectingSceneSession.role)
    }

    func applicationWillResignActive(_ application: UIApplication) {
        // Sent when the application is about to move from active to inactive state. This can occur for certain types of temporary interruptions (such as an incoming phone call or SMS message) or when the user quits the application and it begins the transition to the background state.
        // Use this method to pause ongoing tasks, disable timers, and invalidate graphics rendering callbacks. Games should use this method to pause the game.
    }

    func applicationDidEnterBackground(_ application: UIApplication) {
        // Use this method to release shared resources, save user data, invalidate timers, and store enough application state information to restore your application to its current state in case it is terminated later.
        // If your application supports background execution, this method is called instead of applicationWillTerminate: when the user quits.
    }

    func applicationWillEnterForeground(_ application: UIApplication) {
        // Called as part of the transition from the background to the active state; here you can undo many of the changes made on entering the background.
    }

    func applicationDidBecomeActive(_ application: UIApplication) {
        // Restart any tasks that were paused (or not yet started) while the application was inactive. If the application was previously in the background, optionally refresh the user interface.
    }

    func applicationWillTerminate(_ application: UIApplication) {
        // Called when the application is about to terminate. Save data if appropriate. See also applicationDidEnterBackground:.
    }

    func application(_ app: UIApplication, open url: URL, options: [UIApplication.OpenURLOptionsKey: Any] = [:]) -> Bool {
        // Called when the app was launched with a url. Feel free to add additional processing here,
        // but if you want the App API to support tracking app url opens, make sure to keep this call
        return ApplicationDelegateProxy.shared.application(app, open: url, options: options)
    }

    func application(_ application: UIApplication, continue userActivity: NSUserActivity, restorationHandler: @escaping ([UIUserActivityRestoring]?) -> Void) -> Bool {
        // Called when the app was launched with an activity, including Universal Links.
        // Feel free to add additional processing here, but if you want the App API to support
        // tracking app url opens, make sure to keep this call
        return ApplicationDelegateProxy.shared.application(application, continue: userActivity, restorationHandler: restorationHandler)
    }

}

@available(iOS 13.0, *)
class SceneDelegate: UIResponder, UIWindowSceneDelegate {
    var window: UIWindow?

    func scene(_ scene: UIScene, openURLContexts URLContexts: Set<UIOpenURLContext>) {
        guard let url = URLContexts.first?.url else { return }
        _ = ApplicationDelegateProxy.shared.application(UIApplication.shared, open: url, options: [:])
    }

    func scene(_ scene: UIScene, continue userActivity: NSUserActivity) {
        _ = ApplicationDelegateProxy.shared.application(UIApplication.shared, continue: userActivity, restorationHandler: { _ in })
    }
}

@objc(MainViewController)
class MainViewController: CAPBridgeViewController, WKHTTPCookieStoreObserver {
    private let cookieHostSuffix = "segundajugada.es"
    private let persistedCookiesKeychainAccount = "persistedCookies.v1"
    private let lastUrlDefaultsKey = "lastWebUrl.v1"
    // Persistimos cookies del dominio para mantener sesión en WKWebView incluso si iOS “olvida” el store.
    // Importante: no persistimos contraseñas, solo cookies http.
    private let cookieNamesToExclude: Set<String> = []
    private var cookiePersistDebounce: DispatchWorkItem?

    private func keychainService() -> String {
        return (Bundle.main.bundleIdentifier ?? "es.segundajugada.app").trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func keychainRead(account: String) -> Data? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService(),
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        guard status == errSecSuccess else { return nil }
        return item as? Data
    }

    @discardableResult
    private func keychainWrite(_ data: Data, account: String) -> Bool {
        let baseQuery: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService(),
            kSecAttrAccount as String: account,
        ]

        let updateStatus = SecItemUpdate(baseQuery as CFDictionary, [kSecValueData as String: data] as CFDictionary)
        if updateStatus == errSecSuccess {
            return true
        }

        var addQuery = baseQuery
        addQuery[kSecValueData as String] = data
        let addStatus = SecItemAdd(addQuery as CFDictionary, nil)
        return addStatus == errSecSuccess
    }

    private func shouldPersistCookie(_ cookie: HTTPCookie) -> Bool {
        let name = cookie.name.trimmingCharacters(in: .whitespacesAndNewlines)
        if cookieNamesToExclude.contains(name) { return false }
        let domain = cookie.domain.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if domain == cookieHostSuffix { return true }
        if domain.hasSuffix("." + cookieHostSuffix) { return true }
        return false
    }

    private func serializeCookie(_ cookie: HTTPCookie) -> [String: Any] {
        var payload: [String: Any] = [
            "name": cookie.name,
            "value": cookie.value,
            "domain": cookie.domain,
            "path": cookie.path,
            "secure": cookie.isSecure,
        ]
        if let expires = cookie.expiresDate {
            payload["expires"] = expires.timeIntervalSince1970
        }
        if let sameSite = cookie.properties?[.sameSitePolicy] as? String, !sameSite.isEmpty {
            payload["sameSite"] = sameSite
        }
        return payload
    }

    private func deserializeCookie(_ payload: [String: Any]) -> HTTPCookie? {
        let name = String(payload["name"] as? String ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let value = String(payload["value"] as? String ?? "")
        let domain = String(payload["domain"] as? String ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let path = String(payload["path"] as? String ?? "/").trimmingCharacters(in: .whitespacesAndNewlines)
        if name.isEmpty || domain.isEmpty {
            return nil
        }

        var properties: [HTTPCookiePropertyKey: Any] = [
            .name: name,
            .value: value,
            .domain: domain,
            .path: path.isEmpty ? "/" : path,
        ]
        if let expires = payload["expires"] as? Double, expires > 0 {
            properties[.expires] = Date(timeIntervalSince1970: expires)
        }
        if let secure = payload["secure"] as? Bool, secure {
            properties[.secure] = "TRUE"
        }
        if let sameSite = payload["sameSite"] as? String, !sameSite.isEmpty {
            properties[.sameSitePolicy] = sameSite
        }
        return HTTPCookie(properties: properties)
    }

    private func restorePersistedCookies(_ completion: @escaping (Bool) -> Void) {
        guard let webView = webView else { completion(false); return }
        guard let data = keychainRead(account: persistedCookiesKeychainAccount) else { completion(false); return }
        guard
            let decoded = try? JSONSerialization.jsonObject(with: data),
            let cookiesPayload = decoded as? [[String: Any]]
        else {
            completion(false)
            return
        }

        let cookieStore = webView.configuration.websiteDataStore.httpCookieStore
        let group = DispatchGroup()
        var restoredAny = false

        for payload in cookiesPayload {
            guard let cookie = deserializeCookie(payload) else { continue }
            if !shouldPersistCookie(cookie) { continue }
            restoredAny = true
            group.enter()
            cookieStore.setCookie(cookie) {
                group.leave()
            }
        }

        group.notify(queue: .main) {
            completion(restoredAny)
        }
    }

    private func persistCookiesNow() {
        guard let webView = webView else { return }
        let cookieStore = webView.configuration.websiteDataStore.httpCookieStore
        cookieStore.getAllCookies { [weak self] cookies in
            guard let self = self else { return }
            let payload = cookies.filter { self.shouldPersistCookie($0) }.map { self.serializeCookie($0) }
            guard let data = try? JSONSerialization.data(withJSONObject: payload, options: []) else { return }
            _ = self.keychainWrite(data, account: self.persistedCookiesKeychainAccount)
        }
    }

    private func isEligibleHost(_ url: URL) -> Bool {
        guard let host = url.host?.lowercased(), !host.isEmpty else { return false }
        return host == cookieHostSuffix || host.hasSuffix("." + cookieHostSuffix)
    }

    private func persistLastUrlNow() {
        guard let url = webView?.url else { return }
        guard url.scheme?.lowercased().hasPrefix("http") == true else { return }
        guard isEligibleHost(url) else { return }
        let absolute = url.absoluteString
        guard !absolute.isEmpty else { return }
        UserDefaults.standard.set(absolute, forKey: lastUrlDefaultsKey)
    }

    private func restoreLastUrlIfNeeded() {
        guard let saved = UserDefaults.standard.string(forKey: lastUrlDefaultsKey), !saved.isEmpty else { return }
        guard let target = URL(string: saved) else { return }
        guard target.scheme?.lowercased().hasPrefix("http") == true else { return }
        guard isEligibleHost(target) else { return }

        // Si estamos en /login o en la home, devolvemos al último punto guardado.
        let current = webView?.url
        let currentPath = current?.path.lowercased() ?? ""
        let isLogin = currentPath.contains("/login")
        let isRoot = currentPath == "/" || currentPath.isEmpty
        if !(isLogin || isRoot) {
            return
        }
        // Evita bucles: no re-navegar a /login como "última url".
        if target.path.lowercased().contains("/login") {
            return
        }

        let request = URLRequest(url: target, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 25)
        webView?.load(request)
    }

    @objc private func appDidEnterBackground() {
        persistCookiesNow()
        persistLastUrlNow()
    }

    @objc private func appWillTerminate() {
        persistCookiesNow()
        persistLastUrlNow()
    }

    @objc private func appWillResignActive() {
        // Se dispara de forma más fiable que willTerminate cuando el usuario cambia de app.
        persistCookiesNow()
        persistLastUrlNow()
    }

    private func schedulePersistCookiesSoon() {
        cookiePersistDebounce?.cancel()
        let work = DispatchWorkItem { [weak self] in
            self?.persistCookiesNow()
        }
        cookiePersistDebounce = work
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0, execute: work)
    }

    // WKHTTPCookieStoreObserver
    func cookiesDidChange(in cookieStore: WKHTTPCookieStore) {
        schedulePersistCookiesSoon()
    }

    override func capacitorDidLoad() {
        super.capacitorDidLoad()

        NotificationCenter.default.addObserver(self, selector: #selector(appDidEnterBackground), name: UIApplication.didEnterBackgroundNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(appWillTerminate), name: UIApplication.willTerminateNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(appWillResignActive), name: UIApplication.willResignActiveNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(appDidBecomeActive), name: UIApplication.didBecomeActiveNotification, object: nil)

        // Observa cambios de cookies para persistir justo tras el login (o refresh token) sin depender
        // de que el usuario cierre la app “bien”.
        if #available(iOS 11.0, *) {
            webView?.configuration.websiteDataStore.httpCookieStore.add(self)
        }

        restorePersistedCookies { [weak self] restored in
            guard let self = self else { return }
            guard restored else {
                // Aunque no haya cookies restauradas, intentamos volver a la última URL para no "reiniciar" siempre en onboarding/home.
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) { [weak self] in
                    self?.restoreLastUrlIfNeeded()
                }
                return
            }
            // Evita quedarse en /login/ si la cookie existe pero WKWebView la "pierde" al arrancar.
            if let urlString = self.webView?.url?.absoluteString, urlString.contains("/login") {
                self.webView?.reload()
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) { [weak self] in
                self?.restoreLastUrlIfNeeded()
            }
        }

        // Algunas webs remotas incluyen `@capacitor/core` (web) y pisan `window.Capacitor`.
        // En iOS nativo, Capacitor añade `triggerEvent` desde `native-bridge.js`; si se pierde,
        // el bridge puede intentar lanzar eventos y provocar errores de JS eval.
        let triggerEventPolyfill = """
        (function() {
          var win = window;
          var cap = (win.Capacitor = win.Capacitor || {});
          cap.Plugins = cap.Plugins || {};

          if (typeof cap.createEvent !== 'function') {
            cap.createEvent = function(eventName, eventData) {
              var doc = win.document;
              if (!doc) { return null; }
              var ev = doc.createEvent('Events');
              ev.initEvent(eventName, false, false);
              if (eventData && typeof eventData === 'object') {
                for (var key in eventData) {
                  if (Object.prototype.hasOwnProperty.call(eventData, key)) {
                    ev[key] = eventData[key];
                  }
                }
              }
              return ev;
            };
          }

          if (typeof cap.triggerEvent !== 'function') {
            cap.triggerEvent = function(eventName, target, eventData) {
              var doc = win.document;
              eventData = eventData || {};
              var ev = cap.createEvent(eventName, eventData);
              if (!ev) { return false; }
              if (target === 'document' && doc && doc.dispatchEvent) {
                return doc.dispatchEvent(ev);
              }
              if (target === 'window' && win.dispatchEvent) {
                return win.dispatchEvent(ev);
              }
              if (doc && doc.querySelector) {
                var targetEl = doc.querySelector(target);
                if (targetEl) { return targetEl.dispatchEvent(ev); }
              }
              return false;
            };
          }
        })();
        """
        let polyfillScript = WKUserScript(source: triggerEventPolyfill, injectionTime: .atDocumentStart, forMainFrameOnly: true)
        webView?.configuration.userContentController.addUserScript(polyfillScript)

        // Muchos sitios usan `target="_blank"`/`window.open()` para navegación (o popups OAuth).
        // En WKWebView eso suele crear un "popup" que Capacitor redirige fuera, y a veces parece que "no hace nada".
        // Forzamos que, como mínimo, las aperturas sin URL (about:blank) y las del mismo dominio naveguen en la misma WebView.
        let sameWindowOpen = """
        (function() {
          var win = window;
          var originalOpen = win.open;
          function resolve(url) {
            try { return new URL(url, win.location.href); } catch (e) { return null; }
          }
          win.open = function(url, target, features) {
            try {
              if (!url || url === 'about:blank') {
                return win;
              }
              var resolved = resolve(url);
              if (resolved && resolved.origin === win.location.origin) {
                win.location.href = resolved.href;
                return win;
              }
            } catch (e) {}
            return originalOpen ? originalOpen.call(win, url, target, features) : null;
          };
        })();
        """
        let sameWindowOpenScript = WKUserScript(source: sameWindowOpen, injectionTime: .atDocumentStart, forMainFrameOnly: true)
        webView?.configuration.userContentController.addUserScript(sameWindowOpenScript)

        // La web cargada por `server.url` no siempre puede (o quiere) llamar a SplashScreen.hide().
        // Inyectamos un script que lo intenta al terminar de cargar el documento para evitar el warning:
        // "SplashScreen was automatically hidden after default timeout".
        let source = """
        (function() {
          var tries = 0;
          var maxTries = 600;
          function tryHide() {
            try {
              var splash = window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.SplashScreen;
              if (splash && typeof splash.hide === 'function') {
                splash.hide();
                return true;
              }
            } catch (e) {}
            return false;
          }
          if (tryHide()) { return; }
          var timer = setInterval(function() {
            tries++;
            if (tryHide() || tries >= maxTries) {
              clearInterval(timer);
            }
          }, 50);
        })();
        """

        let script = WKUserScript(source: source, injectionTime: .atDocumentEnd, forMainFrameOnly: true)
        webView?.configuration.userContentController.addUserScript(script)
    }

    @objc private func appDidBecomeActive() {
        // iOS puede matar el proceso al bloquear o por memoria; al volver, restauramos la última ruta conocida.
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) { [weak self] in
            self?.restoreLastUrlIfNeeded()
        }
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        // Para sesiones/partidos: evita autolock por inactividad (muy útil en iPad durante el registro).
        UIApplication.shared.isIdleTimerDisabled = true
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        UIApplication.shared.isIdleTimerDisabled = false
    }
}
