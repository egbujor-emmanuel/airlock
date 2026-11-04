// Re-send events to a merchant after a fix: `node sender/redeliver.js <merchant> [count]`.
// Merchant endpoints, regions and shared webhook secrets live in merchants.local.json
// (PayCo's own copy; generated per machine for the demo, never committed).
const fs = require("node:fs");
const path = require("node:path");
const { deliver } = require("./dispatch");

async function main() {
  const [merchantName = "acme", count = "5"] = process.argv.slice(2);
  const merchants = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "merchants.local.json"), "utf8"));
  const merchant = merchants[merchantName];
  if (!merchant) throw new Error(`no merchant ${merchantName} in merchants.local.json`);
  const results = [];
  for (let i = 0; i < Number(count); i += 1) {
    const event = { id: `evt_redeliver_${Date.now()}_${i}`, type: "payment.succeeded", amount: 1000 + i };
    results.push(await deliver(merchant.url, event, merchant));
  }
  const ok = results.filter((s) => s === 200).length;
  process.stdout.write(
    `redelivered ${results.length} ${merchant.region} events to ${merchantName}: ${ok} accepted, ${results.length - ok} rejected\n`,
  );
}

main().catch((err) => {
  process.stderr.write(`${err.message}\n`);
  process.exit(1);
});
