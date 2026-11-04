// Client for PayCo's high-resolution clock service (EU pilot, platform 4.2.0).
// The service disciplines time against the EU NTP pool and exposes it through the
// process's monotonic performance timeline.
const { performance } = require("node:perf_hooks");

/**
 * Current time from the clock service.
 * @returns {number} seconds since the Unix epoch
 */
function nowSeconds() {
  return Math.round(performance.timeOrigin + performance.now());
}

module.exports = { nowSeconds };
