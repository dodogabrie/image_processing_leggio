const sharp = require('sharp');
const fs = require('fs');
const path = require('path');
const { stat } = fs.promises;
const [input, output] = process.argv.slice(2);

(async () => {
  try {
    const { size } = await stat(input); // in byte
    const originalKB = size / 1024;

    // nuova formula: più aggressiva per input > 1MB
    let quality = Math.round(90 - originalKB / 25);
    quality = Math.max(20, Math.min(quality, 90));

    console.log(generoErrore)
    const buffer = await sharp(input).webp({ quality }).toBuffer();
    await fs.promises.writeFile(output, buffer);
    console.log(`Converted: ${input} → ${output} (quality=${quality}, ${(buffer.length / 1024).toFixed(1)} KB)`);
    process.exit(0);
  } catch (err) {
    console.error(err.stack || err.message);
    // Scrivi anche su file di log nella cartella di output
    try {
      const outDir = path.dirname(output);
      if (!fs.existsSync(outDir)) {
        fs.mkdirSync(outDir, { recursive: true });
      }
      const logPath = path.join(outDir, 'worker_error_log.txt');
      const logMsg = `[${new Date().toISOString()}] ${input} → ${output}\n${err.stack || err.message}\n\n`;
      fs.appendFileSync(logPath, logMsg);
    } catch (e) {
      // Ignora errori di scrittura log
    }
    process.exit(1);
  }
})();
