const sharp = require('sharp');
const fs = require('fs');
const path = require('path');
const { stat } = fs.promises;
const [input, output] = process.argv.slice(2);

(async () => {
  const logError = (err) => {
    console.error(err.stack || err.message);
    try {
      const outDir = path.dirname(output || './');
      if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
      const logPath = path.join(outDir, 'worker_error_log.txt');
      const logMsg = `[${new Date().toISOString()}] ${input} → ${output}\n${err.stack || err.message}\n\n`;
      fs.appendFileSync(logPath, logMsg);
    } catch (_) {}
  };

  try {
    if (fs.existsSync(output)) {
      console.error(`Output file already exists: ${output}`);
      process.exit(0);
    }

    const { size } = await stat(input);
    const originalKB = size / 1024;

    let quality = Math.round(90 - originalKB / 27.3);
    quality = Math.max(15, Math.min(quality, 90));

    const info = await sharp(input)
      .webp({
        quality,
        effort: 6,
        smartSubsample: true,
        preset: 'photo',
        nearLossless: false
      })
      .toFile(output);

    console.log(
      `Converted: ${input} → ${output} ` +
      `(quality=${quality}, ${(info.size / 1024).toFixed(1)} KB)`
    );

    process.exit(0);
  } catch (err) {
    logError(err);
    process.exit(1);
  }
})();
