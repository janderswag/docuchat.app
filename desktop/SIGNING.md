# Signed, trustworthy downloads — what to buy and run (P2.7)

The build scripts are ready on both platforms; certificates are the only missing input.
This file is the exact checklist. Steps marked **[JAKE]** need a purchase or an
interactive login and cannot be done by an agent session.

## macOS (Developer ID + notarization)

1. **[JAKE] Join the Apple Developer Program** ($99/year) at developer.apple.com with
   your Apple ID. Takes minutes to a day to activate.
2. **[JAKE] Create a "Developer ID Application" certificate**: Xcode > Settings >
   Accounts > Manage Certificates > + > Developer ID Application (or via
   developer.apple.com > Certificates). It lands in your login keychain. Find its exact
   name with:

       security find-identity -v -p codesigning

   Export it as an env var for the build:

       export APPLE_DEV_ID_APP='Developer ID Application: Your Name (TEAMID1234)'

3. **[JAKE] Store a notarytool credential** (one time; needs an app-specific password
   from appleid.apple.com > Sign-In and Security > App-Specific Passwords):

       xcrun notarytool store-credentials docuchat-notary \
         --apple-id you@example.com --team-id TEAMID1234 --password <app-specific>
       export NOTARY_PROFILE=docuchat-notary

4. **Build, sign, notarize, staple — one command** (agent-runnable once 2-3 are done):

       pip install pyinstaller pywebview   # in the project venv, once
       BUNDLE_OLLAMA=1 ./desktop/build_macos.sh

   Output: `dist/docuchat.dmg`, notarized + stapled. Double-click installs with no
   Gatekeeper block. Without the env vars the same script produces
   `dist/docuchat-unsigned.dmg` for local testing (right-click > Open to bypass
   Gatekeeper on your own machine only).

5. **Verify the bundle before shipping** (fresh user account or a second Mac):
   open the app, complete the wizard (it downloads the models in-app), ask the sample
   matter a suggested question, confirm a cited answer. Also confirm
   `spctl --assess --type execute -v dist/docuchat.app` says "accepted".

## Windows (Authenticode)

PyInstaller does not cross-compile: build on the Windows box using the existing
`desktop\build_windows.ps1` (see `desktop/WINDOWS_TEST.md`), then sign.

1. **[JAKE] Pick a signing route** (either works with `signtool`):
   - **Azure Trusted Signing** (recommended, ~$9.99/month): Azure account >
     "Trusted Signing" resource > identity validation (individual validation is
     supported). Microsoft-managed cert; good SmartScreen standing.
   - **OV code-signing certificate** (~$200-400/year from Sectigo/SSL.com/Certum;
     ships on a hardware token since 2023). EV builds SmartScreen reputation fastest.
2. **[JAKE] Identity validation** with the chosen provider (passport/ID; 1-3 days).
3. **Sign** (agent-runnable once the cert exists), e.g. with a local/token cert:

       signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 ^
         /a dist\docuchat-setup\docuchat-setup.exe

   (Azure Trusted Signing instead uses `signtool` with the Trusted Signing dlib per
   Microsoft's docs — their quickstart has the exact command.)
4. **SmartScreen expectations:** even correctly signed OV binaries can show "unrecognized
   app" until enough installs build reputation. This fades with downloads; EV or
   Trusted Signing shortens it. Do not chase it with tricks — ship, and it clears.

## Release checklist (both platforms)

- [ ] Bump `CFBundleShortVersionString` (mac spec) / exe version (win spec).
- [ ] `git tag vX.Y.Z && git push --tags`.
- [ ] `gh release create vX.Y.Z dist/docuchat.dmg` (and later the signed `.exe`).
- [ ] Only AFTER the artifact is live: flip the site's download section to "available"
      for that platform (deploy-approval rule applies — owner preview first).
