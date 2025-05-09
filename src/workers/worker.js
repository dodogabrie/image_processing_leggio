const sharp = require('sharp');
const fs = require('fs');
const path = require('path');
const { stat } = fs.promises;
const [input, output] = process.argv.slice(2);

(async () => {
  try {
    // Se il file di output esiste già, esci subito
    if (fs.existsSync(output)) {
      console.error(`Output file already exists: ${output}`);
      process.exit(0);
    }

    const { size } = await stat(input); // in byte
    const originalKB = size / 1024;

    let quality = Math.round(90 - originalKB / 27.3);
    quality = Math.max(15, Math.min(quality, 90));

    const info = await sharp(input)
      .webp({
        quality,
        effort: 6,           // massimo sforzo di compressione (più lento, più piccolo)
        smartSubsample: true,
        preset: 'photo',     // ottimizzato per fotografie
        nearLossless: false  // disabilita near-lossless per massima compressione
      })
      .toFile(output);

    console.log(
      `Converted: ${input} → ${output} ` +
      `(quality=${quality}, ${(info.size/1024).toFixed(1)} KB)`
    );

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
