// Per-region clocks for webhook dispatch. Platform 4.2.0 moved each region onto its
// own clock source so dispatch can follow the region's NTP pool.
//
// Every clock returns the signing timestamp for the `t=` field of PayCo-Signature,
// in whole seconds since the Unix epoch.
const hrclock = require("./hrclock");

const clocks = {
  "us-east": () => Math.floor(Date.now() / 1000),
  "ap-south": () => Math.floor(Date.now() / 1000),
  "eu-west": () => hrclock.nowSeconds(),
};

/** @param {string} region @returns {number} */
function signingTimestamp(region) {
  const clock = clocks[region];
  if (!clock) throw new Error(`no dispatch clock for region ${region}`);
  return clock();
}

module.exports = { signingTimestamp, REGIONS: Object.keys(clocks) };
