# MyCon Learn for iPhone

A native iOS app wrapping the same interface as the web app, running entirely
offline. No server, no Wi-Fi, no laptop — the vocabulary is compiled into the
app and progress is saved on the phone.

Building it needs **Xcode** and a **free Apple ID**. No paid developer account,
no Node, no CocoaPods.

---

## How it fits together

`static/index.html` stays the single source of truth for the interface. The
build script rewrites it to run without a backend and drops the result in
`MyConLearn/www/`, where a small Swift app loads it in a web view:

```
static/index.html  ─┐
                    ├─→  scripts/build_ios_www.py  ─→  ios/MyConLearn/www/  ─→  the app
vocab/*.csv        ─┘
```

`www/local-api.js` is a JavaScript port of `app/main.py`: it intercepts the
page's `/api/*` calls and answers them from the compiled vocabulary. The two
implementations are held together by `tests/test_offline_parity.py`, which
replays several thousand requests through both and fails if any response
differs.

| File | Role |
|---|---|
| `MyConLearn/MyConLearnApp.swift` | App entry point |
| `MyConLearn/WebAppView.swift` | Hosts the web view |
| `MyConLearn/AppContentSchemeHandler.swift` | Serves `www/` over a `myconlearn://` origin |
| `MyConLearn/ProgressStore.swift` | Mirrors progress outside the web view |
| `MyConLearn/www/` | The offline bundle (`index.html` and `vocab.js` are generated) |

---

## Try it before installing anything

The offline bundle is a normal web page, so you can check it in a browser
first — no Xcode required:

```bash
poetry run python scripts/build_ios_www.py
python3 -m http.server 8080 --directory ios/MyConLearn/www
```

Open <http://localhost:8080>. In Safari or Chrome, switch on the responsive
design view and pick an iPhone to see the phone layout. This is the exact
bundle the app ships.

---

## One-time setup

1. **Install Xcode** from the Mac App Store (it is large, ~7 GB). Open it once
   and accept the licence.

2. **Add your Apple ID**: Xcode → Settings → Accounts → **+** → Apple ID. Any
   ordinary Apple ID works; you do not need the paid programme.

3. **Open the project**: double-click `ios/MyConLearn.xcodeproj`.

4. **Choose your signing team**: select the **MyConLearn** target →
   **Signing & Capabilities** → set **Team** to `Your Name (Personal Team)`.

   If Xcode reports that the bundle identifier is unavailable, change
   **Bundle Identifier** to something unique, for example
   `com.yourname.myconlearn`.

   > Settle on a bundle identifier now and leave it alone. iOS files an app's
   > data under its bundle identifier, so changing it later looks exactly like
   > a fresh install: the app comes back with no progress.

5. **Plug in your iPhone** with a cable, unlock it, and tap **Trust This
   Computer**. Pick the phone from the device menu at the top of the Xcode
   window, where the simulator is currently selected.

6. **Turn on Developer Mode** (iOS 16 and later). The option only appears once
   Xcode has tried to talk to the phone, so press **Run** (⌘R) once and let it
   fail. Then on the phone: Settings → Privacy & Security → **Developer Mode**
   → on. The phone restarts and asks you to confirm after unlocking.

7. **Press Run** again. The first build takes a minute or two.

8. **Trust the certificate on the phone**: the first launch is refused with
   "Untrusted Developer". Go to Settings → General → VPN & Device Management →
   your Apple ID → **Trust**. Then launch MyCon Learn from the Home Screen.

After the first cable install you can tick **Connect via network** on the
device in Xcode's Devices window and install over Wi-Fi from then on.

---

## The weekly reinstall

Apps signed with a free Apple ID stop launching after **seven days**. To
refresh: connect the phone, open the project, press **Run**.

**Your progress is kept.** Running from Xcode installs over the existing app
and leaves its data container untouched. Progress is only lost if you *delete*
the app from the Home Screen, or change the bundle identifier.

A free Apple ID also allows at most three apps installed at a time, and ten new
app identifiers per seven days. Neither matters if MyCon Learn is the only app
you sideload.

If the weekly reinstall ever grates, a paid Apple Developer Program membership
(currently $99/year) raises the certificate lifetime to a year and unlocks
TestFlight, which would let you install over the air without a Mac. Nothing in
this project changes — it is the same build, signed differently.

---

## Changing what you practise

Edit the CSVs in `vocab/` exactly as before, then:

```bash
poetry run python scripts/build_ios_www.py
```

and press **Run** in Xcode. Since this is also roughly the weekly cadence of
the signing refresh, the two chores fold into one.

Adding a brand new CSV file needs no changes in Xcode: `www` is a folder
reference, so whatever the build script writes there is bundled.

Progress is keyed by the words themselves, not by database row, so adding,
reordering or removing entries leaves your mastered words alone. Correcting a
typo in an existing word makes it a new word, which starts unmastered.

Cards added with **+ Add New Card** inside the app live only on the phone. Add
them to a CSV as well if you want them on the web app too.

---

## Where progress lives

Two copies, both inside the app's data container:

- `localStorage`, written by the page itself
- `Application Support/mycon-progress.json`, written by `ProgressStore.swift`
  every time the page saves

The second exists because iOS may evict web storage when the device is short
on space. When the page starts and finds `localStorage` empty, it restores from
the mirror. The mirror is also included in device backups, so progress follows
you to a new phone.

`tests/test_webview_integration.py` proves this end to end: it answers a card,
destroys the web view's storage entirely, reloads, and checks the mastered word
is still there.

---

## Troubleshooting

**"Signing for MyConLearn requires a development team"** — step 4 above.

**"Unable to install… bundle identifier is not available"** — someone else has
registered that identifier. Change it to something personal (step 4).

**The app quits immediately, about a week after installing** — the free signing
certificate expired. Press Run in Xcode again.

**A blank white screen** — `www/` is missing or stale. Run
`poetry run python scripts/build_ios_www.py`, then Product → Clean Build Folder
(⇧⌘K) and Run again.

**New words are not showing up** — the build script has not been run since you
edited the CSVs. `poetry run pytest tests/test_ios_project.py` fails loudly
when the bundle is stale.
