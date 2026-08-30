/*
 * Replays the request list in REQUESTS (injected by the Python test) through
 * the patched window.fetch and prints the results as JSON after a sentinel
 * line, so incidental output cannot corrupt the payload.
 */
(function () {
    var results = [];
    var index = 0;

    function finish() {
        print("---RESULT---");
        print(JSON.stringify(results));
    }

    function next() {
        if (index >= REQUESTS.length) {
            finish();
            return;
        }

        var spec = REQUESTS[index++];
        var init = { method: spec.method };
        if (spec.body !== undefined && spec.body !== null) {
            init.body = JSON.stringify(spec.body);
        }

        window.fetch(spec.url, init).then(function (response) {
            return response.json().then(function (data) {
                results.push({ name: spec.name, status: response.status, data: data });
                next();
            });
        });
    }

    next();

    if (typeof drainMicrotasks === "function") {
        drainMicrotasks();
    }
})();
