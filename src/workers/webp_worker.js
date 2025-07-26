const sharp = require('sharp');
const fs = require('fs').promises;
const path = require('path');
const { stat } = fs;
const [input, output] = process.argv.slice(2);

(async () => {
  const logError = async (err) => {
    console.error(err.stack || err.message);
    try {
      // Non creare più la directory qui, si assume già esista
      const outDir = path.dirname(output || './');
      const logPath = path.join(outDir, 'worker_error_log.txt');
      const logMsg = `[${new Date().toISOString()}] ${input} → ${output}\n${err.stack || err.message}\n\n`;
      await fs.appendFile(logPath, logMsg);
    } catch (_) {}
  };

  try {
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
    await logError(err);
    process.exit(1);
  }
})();
