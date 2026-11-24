# Mod Garage Studio — Android APK

This Android app wraps the published Mod Garage Studio website in a WebView.

## Build APK
1. Open the repository's **Actions** tab.
2. Select **Build Mod Garage Studio APK**.
3. Tap **Run workflow** on branch `apk/mod-garage-studio-webview`.
4. When the run completes, open its **Artifacts** section and download `Mod-Garage-Studio-debug-APK`.
5. Extract the artifact ZIP and install `app-debug.apk`.

## Notes
- This is an online WebView wrapper. An internet connection is required.
- File selection is enabled for importing files into the website.
- The APK is debug-signed by the Android Gradle build and is suitable for direct testing.
- This wrapper does not directly modify protected game binaries or install mods into the game.
