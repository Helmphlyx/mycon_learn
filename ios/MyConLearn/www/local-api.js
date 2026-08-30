/*
 * local-api.js — offline replacement for the FastAPI backend.
 *
 * Intercepts window.fetch for /api/* and answers from bundled vocabulary
 * (vocab.js) plus progress kept in localStorage, mirrored to native storage
 * so it survives a WebKit data purge or a re-signed reinstall.
 *
 * Logic here is a direct port of app/main.py + app/vocab_loader.py. Keep the
 * two in sync: the same UI (static/index.html) runs against both.
 */
(function () {
    "use strict";

    var STATE_KEY = "mycon.state.v1";

    // ---------------------------------------------------------------- helpers

    // Mirrors Python's str.split() with no argument: split on runs of
    // whitespace, discarding empty leading/trailing fields.
    function pySplit(text) {
        var trimmed = text.trim();
        return trimmed === "" ? [] : trimmed.split(/\s+/);
    }

    // Python len() counts code points, JS .length counts UTF-16 units.
    function codePointLength(text) {
        return Array.from(text).length;
    }

    function firstCodePoint(text) {
        return Array.from(text)[0] || "";
    }

    function repeat(char, count) {
        return count > 0 ? new Array(count + 1).join(char) : "";
    }

    // Port of normalize_vietnamese() — strip, lowercase, NFC. Order matters.
    function normalizeVietnamese(text) {
        return String(text).trim().toLowerCase().normalize("NFC");
    }

    // Stable identity for a card, so progress survives the id renumbering that
    // happens whenever the vocab CSVs are rebuilt into the app.
    function cardKey(vietnamese, english) {
        return (
            String(vietnamese).normalize("NFC") +
            "␟" +
            String(english).normalize("NFC")
        );
    }

    function nowIso() {
        return new Date().toISOString();
    }

    // ---------------------------------------------------------------- storage

    var state = { progress: {}, customCards: [] };

    function loadState() {
        var raw = null;
        try {
            raw = window.localStorage.getItem(STATE_KEY);
        } catch (err) {
            raw = null;
        }

        // localStorage lost (cleared, evicted, or a fresh install over an old
        // data container) — fall back to whatever the native side kept.
        if (!raw && typeof window.__MYCON_RESTORED__ === "string" && window.__MYCON_RESTORED__) {
            raw = window.__MYCON_RESTORED__;
        }

        if (!raw) return;

        try {
            var parsed = JSON.parse(raw);
            if (parsed && typeof parsed === "object") {
                state.progress = parsed.progress && typeof parsed.progress === "object" ? parsed.progress : {};
                state.customCards = Array.isArray(parsed.customCards) ? parsed.customCards : [];
            }
        } catch (err) {
            console.warn("Could not parse saved progress, starting fresh:", err);
        }
    }

    function saveState() {
        var json = JSON.stringify(state);
        try {
            window.localStorage.setItem(STATE_KEY, json);
        } catch (err) {
            console.warn("localStorage write failed:", err);
        }
        try {
            if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.myconProgress) {
                window.webkit.messageHandlers.myconProgress.postMessage(json);
            }
        } catch (err) {
            /* not running inside the iOS shell */
        }
    }

    function progressFor(card) {
        var key = cardKey(card.vietnamese, card.english);
        if (!state.progress[key]) {
            state.progress[key] = { mastered: false, success_count: 0, fail_count: 0, last_reviewed: null };
        }
        return state.progress[key];
    }

    // ------------------------------------------------------------------ cards

    var cards = [];
    var cardsById = {};

    function buildCards() {
        var bundled = (window.MYCON_VOCAB && window.MYCON_VOCAB.cards) || [];
        var all = [];
        var seen = {};

        function push(vietnamese, english, category, difficulty) {
            var key = cardKey(vietnamese, english);
            // Port of load_topic_into_db(): same vietnamese + english is skipped.
            if (seen[key]) return;
            seen[key] = true;
            all.push({
                id: all.length + 1,
                vietnamese: vietnamese,
                english: english,
                category: category || null,
                difficulty_level: difficulty || 1
            });
        }

        bundled.forEach(function (row) {
            push(row.v, row.e, row.c, row.d);
        });
        state.customCards.forEach(function (row) {
            push(row.v, row.e, row.c, row.d);
        });

        cards = all;
        cardsById = {};
        cards.forEach(function (card) {
            cardsById[card.id] = card;
        });
    }

    // Shape returned by CardResponse in app/schemas.py.
    function cardResponse(card) {
        var progress = progressFor(card);
        return {
            id: card.id,
            vietnamese: card.vietnamese,
            english: card.english,
            category: card.category,
            difficulty_level: card.difficulty_level,
            success_count: progress.success_count,
            fail_count: progress.fail_count,
            last_reviewed: progress.last_reviewed,
            mastered: progress.mastered
        };
    }

    // ------------------------------------------------------------------- logic

    // Port of generate_hint().
    function generateHint(card, mode, hintLevel) {
        var answer = mode === "eng_to_viet" ? card.vietnamese : card.english;
        var words = pySplit(answer);

        if (hintLevel === 1) {
            return words
                .map(function (word) {
                    var len = codePointLength(word);
                    return repeat("_", len) + "(" + len + ")";
                })
                .join(" ");
        }
        if (hintLevel === 2) {
            return words
                .map(function (word) {
                    return firstCodePoint(word) + repeat("_", codePointLength(word) - 1);
                })
                .join(" ");
        }
        return answer;
    }

    // Port of the word-by-word partial credit block in check_answer().
    function partialCredit(card, userInput) {
        var best = { hint: null, correct: 0, total: 0 };
        var userWords = pySplit(userInput);

        [card.vietnamese, card.english].forEach(function (candidate) {
            var expectedWords = pySplit(candidate);
            if (expectedWords.length < 2 || userWords.length < 1) return;

            var hintParts = [];
            var matched = 0;
            expectedWords.forEach(function (expectedWord, i) {
                if (i < userWords.length && normalizeVietnamese(userWords[i]) === normalizeVietnamese(expectedWord)) {
                    hintParts.push(expectedWord);
                    matched += 1;
                } else {
                    hintParts.push(repeat("_", codePointLength(expectedWord)));
                }
            });

            if (matched > best.correct) {
                best = { hint: hintParts.join(" "), correct: matched, total: expectedWords.length };
            }
        });

        return best.correct > 0 ? best : null;
    }

    // ----------------------------------------------------------------- routes

    function json(body, status) {
        return new Response(JSON.stringify(body), {
            status: status || 200,
            headers: { "Content-Type": "application/json" }
        });
    }

    function notFound(detail) {
        return json({ detail: detail }, 404);
    }

    function requireCard(cardId) {
        return cardsById[cardId] || null;
    }

    var routes = {
        "GET /api/categories": function () {
            var seen = {};
            var result = [];
            cards.forEach(function (card) {
                if (card.category && !seen[card.category]) {
                    seen[card.category] = true;
                    result.push(card.category);
                }
            });
            return json(result);
        },

        "GET /api/topics": function () {
            return json(((window.MYCON_VOCAB && window.MYCON_VOCAB.topics) || []).map(function (topic) {
                return { name: topic.name, filename: topic.filename };
            }));
        },

        "GET /api/cards": function (url) {
            var category = url.searchParams.get("category");
            var skip = parseInt(url.searchParams.get("skip") || "0", 10);
            var limit = parseInt(url.searchParams.get("limit") || "100", 10);
            var matching = cards.filter(function (card) {
                return !category || card.category === category;
            });
            return json(matching.slice(skip, skip + limit).map(cardResponse));
        },

        "GET /api/card/random": function (url) {
            var mode = url.searchParams.get("mode") || "eng_to_viet";
            var category = url.searchParams.get("category");
            var matching = cards.filter(function (card) {
                return !category || card.category === category;
            });
            if (matching.length === 0) return notFound("No cards available");

            var card = matching[Math.floor(Math.random() * matching.length)];
            return json({
                id: card.id,
                prompt: mode === "eng_to_viet" ? card.english : card.vietnamese,
                mode: mode,
                category: card.category
            });
        },

        "GET /api/stats": function () {
            var totalSuccess = 0;
            var totalFail = 0;
            cards.forEach(function (card) {
                var progress = progressFor(card);
                totalSuccess += progress.success_count;
                totalFail += progress.fail_count;
            });
            var totalAttempts = totalSuccess + totalFail;
            return json({
                total_cards: cards.length,
                total_attempts: totalAttempts,
                total_success: totalSuccess,
                total_fail: totalFail,
                accuracy: totalAttempts > 0 ? Math.round((totalSuccess / totalAttempts) * 1000) / 10 : 0
            });
        },

        "POST /api/check": function (url, body) {
            var card = requireCard(body.card_id);
            if (!card) return notFound("Card not found");

            var userNormalized = normalizeVietnamese(body.user_input);
            var correctViet = userNormalized === normalizeVietnamese(card.vietnamese);
            var correctEng = userNormalized === normalizeVietnamese(card.english);
            var correct = correctViet || correctEng;

            if (body.record_result || correct) {
                var progress = progressFor(card);
                progress.last_reviewed = nowIso();
                if (correct) {
                    progress.success_count += 1;
                    if (body.mark_mastered) progress.mastered = true;
                } else {
                    progress.fail_count += 1;
                }
                saveState();
            }

            var expected = null;
            var partial = null;
            if (correct) {
                expected = correctViet ? card.vietnamese : card.english;
            } else {
                partial = partialCredit(card, body.user_input);
            }

            return json({
                correct: correct,
                expected: expected,
                user_input: body.user_input,
                diff: null,
                attempts: null,
                partial_hint: partial ? partial.hint : null,
                correct_count: partial ? partial.correct : null,
                total_words: partial ? partial.total : null
            });
        },

        "POST /api/give_up": function (url, body) {
            var card = requireCard(body.card_id);
            if (!card) return notFound("Card not found");

            var progress = progressFor(card);
            progress.last_reviewed = nowIso();
            progress.fail_count += 1;
            saveState();

            return json({ answer: card.vietnamese, vietnamese: card.vietnamese, english: card.english });
        },

        "POST /api/hint": function (url, body) {
            var card = requireCard(body.card_id);
            if (!card) return notFound("Card not found");

            var mode = url.searchParams.get("mode") || "eng_to_viet";
            var hintLevel = Math.max(1, Math.min(3, body.hint_level));
            return json({ hint: generateHint(card, mode, hintLevel), hint_level: hintLevel });
        },

        "POST /api/mastery/reset": function (url, body) {
            var category = body && body.category ? body.category : null;
            var count = 0;
            cards.forEach(function (card) {
                if (category && card.category !== category) return;
                var progress = progressFor(card);
                if (progress.mastered) count += 1;
                progress.mastered = false;
            });
            saveState();

            var label = category ? '"' + category + '"' : "all topics";
            return json({ message: "Reset mastery for " + count + " cards in " + label, cards_reset: count });
        },

        "POST /api/card": function (url, body) {
            var vietnamese = String(body.vietnamese || "").trim();
            var english = String(body.english || "").trim();
            if (!vietnamese || !english) return json({ detail: "Vietnamese and English are required" }, 422);

            state.customCards.push({
                v: vietnamese,
                e: english,
                c: body.category || null,
                d: body.difficulty_level || 1
            });
            saveState();
            buildCards();

            var added = cards.filter(function (card) {
                return card.vietnamese === vietnamese && card.english === english;
            })[0];
            return json(cardResponse(added));
        },

        // Every CSV is compiled into the app at build time, so loading and
        // syncing are already done — report what is bundled instead.
        "POST /api/topics/load": function (url, body) {
            var filename = body.filename;
            var topic = ((window.MYCON_VOCAB && window.MYCON_VOCAB.topics) || []).filter(function (t) {
                return t.filename === filename;
            })[0];
            if (!topic) return notFound("Vocabulary file not found: " + filename);

            return json({
                filename: filename,
                cards_loaded: topic.count,
                message: topic.count + " cards from " + filename + " are already bundled in the app"
            });
        },

        "POST /api/topics/sync": function () {
            var topics = (window.MYCON_VOCAB && window.MYCON_VOCAB.topics) || [];
            var loaded = {};
            topics.forEach(function (topic) {
                loaded[topic.name] = topic.count;
            });
            return json({
                message: "All " + cards.length + " cards from " + topics.length + " files are bundled in the app",
                loaded: loaded
            });
        }
    };

    // ------------------------------------------------------------ fetch shim

    var originalFetch = window.fetch ? window.fetch.bind(window) : null;

    window.fetch = function (input, init) {
        var request = input instanceof Request ? input : null;
        var rawUrl = request ? request.url : String(input);
        var url;
        try {
            url = new URL(rawUrl, window.location.href);
        } catch (err) {
            return originalFetch ? originalFetch(input, init) : Promise.reject(err);
        }

        if (!url.pathname.startsWith("/api/")) {
            return originalFetch ? originalFetch(input, init) : Promise.reject(new Error("Offline: " + url.pathname));
        }

        var method = ((init && init.method) || (request && request.method) || "GET").toUpperCase();
        var handler = routes[method + " " + url.pathname];
        if (!handler) {
            return Promise.resolve(notFound("No offline handler for " + method + " " + url.pathname));
        }

        var body = {};
        var rawBody = init && init.body;
        if (typeof rawBody === "string" && rawBody) {
            try {
                body = JSON.parse(rawBody);
            } catch (err) {
                return Promise.resolve(json({ detail: "Invalid JSON body" }, 422));
            }
        }

        try {
            return Promise.resolve(handler(url, body));
        } catch (err) {
            console.error("Offline API error:", err);
            return Promise.resolve(json({ detail: String(err) }, 500));
        }
    };

    // ------------------------------------------------------------------ init

    loadState();
    buildCards();
    // Push the merged state straight back down so a native-side restore is
    // immediately mirrored into localStorage.
    saveState();
})();
