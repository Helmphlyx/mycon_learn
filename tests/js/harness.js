/*
 * Minimal browser shims so ios/MyConLearn/www/local-api.js can run under the
 * JavaScriptCore shell (jsc). Only the surface local-api.js actually touches
 * is implemented. Used by tests/test_offline_parity.py.
 */

var window = this;

window.location = { href: "http://localhost:8000/index.html" };

var console = {
    log: function () {},
    warn: function () {},
    error: function () {}
};
window.console = console;

// --- localStorage -----------------------------------------------------------

var __storage = {};
window.localStorage = {
    getItem: function (key) {
        return Object.prototype.hasOwnProperty.call(__storage, key) ? __storage[key] : null;
    },
    setItem: function (key, value) {
        __storage[key] = String(value);
    },
    removeItem: function (key) {
        delete __storage[key];
    }
};

// --- URL / URLSearchParams --------------------------------------------------

function URLSearchParams(query) {
    this._pairs = [];
    String(query || "")
        .replace(/^\?/, "")
        .split("&")
        .forEach(function (pair) {
            if (!pair) return;
            var eq = pair.indexOf("=");
            var key = eq >= 0 ? pair.slice(0, eq) : pair;
            var value = eq >= 0 ? pair.slice(eq + 1) : "";
            this._pairs.push([
                decodeURIComponent(key.replace(/\+/g, " ")),
                decodeURIComponent(value.replace(/\+/g, " "))
            ]);
        }, this);
}

URLSearchParams.prototype.get = function (name) {
    for (var i = 0; i < this._pairs.length; i++) {
        if (this._pairs[i][0] === name) return this._pairs[i][1];
    }
    return null;
};

function URL(url, base) {
    var full = String(url);

    if (!/^[a-z][a-z0-9+.-]*:/i.test(full)) {
        var origin = /^([a-z][a-z0-9+.-]*:\/\/[^\/]*)/i.exec(String(base || ""));
        if (full.charAt(0) === "/") {
            full = (origin ? origin[1] : "") + full;
        } else {
            full = String(base || "").replace(/[^\/]*$/, "") + full;
        }
    }

    var withoutHash = full.split("#")[0];
    var queryStart = withoutHash.indexOf("?");
    var path = queryStart >= 0 ? withoutHash.slice(0, queryStart) : withoutHash;
    var query = queryStart >= 0 ? withoutHash.slice(queryStart + 1) : "";

    var afterOrigin = /^[a-z][a-z0-9+.-]*:\/\/[^\/]*(\/.*)?$/i.exec(path);
    this.href = full;
    this.pathname = afterOrigin ? afterOrigin[1] || "/" : path;
    this.searchParams = new URLSearchParams(query);
}

window.URL = URL;
window.URLSearchParams = URLSearchParams;

// --- fetch primitives -------------------------------------------------------

function Request() {}
window.Request = Request;

function Response(body, init) {
    this._body = body;
    this.status = (init && init.status) || 200;
    this.ok = this.status >= 200 && this.status < 300;
}

Response.prototype.json = function () {
    return Promise.resolve(JSON.parse(this._body));
};

window.Response = Response;

// local-api.js falls through to the original fetch for non-/api paths; nothing
// in the tests should reach it.
window.fetch = function (input) {
    throw new Error("unexpected network fetch: " + input);
};
