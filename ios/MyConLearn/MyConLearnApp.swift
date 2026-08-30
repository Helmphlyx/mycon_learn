import SwiftUI

@main
struct MyConLearnApp: App {
    var body: some Scene {
        WindowGroup {
            WebAppView()
                // The web page paints its own safe-area padding via
                // env(safe-area-inset-*), so let it own the full screen.
                // Keyboard avoidance is deliberately left on: it keeps the
                // answer field visible while typing.
                .ignoresSafeArea(.container, edges: .all)
                // The UI is a light design only; forcing the scheme keeps the
                // status bar legible.
                .preferredColorScheme(.light)
        }
    }
}
