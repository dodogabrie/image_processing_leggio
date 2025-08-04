import sharp from 'sharp';
import fs from 'fs/promises';
import path from 'path';

const [input, output] = process.argv.slice(2);

if (!input || !output) {
  console.error('Usage: node thumbnail_worker.js <input> <output>');
  process.exit(1);
}

async function logError(err) {
  console.error(err.stack || err.message);
  try {
    // Si assume che la directory di output esista già
    const outDir = path.dirname(output);
    const logPath = path.join(outDir, 'worker_error_log.txt');
    const logMsg =
      `[${new Date().toISOString()}] ${input} → ${output}\n` +
      `${err.stack || err.message}\n\n`;
    await fs.appendFile(logPath, logMsg);
  } catch {
    // Ignora errori di logging
  }
}

(async () => {
  try {
    const stat = await fs.stat(input);
    const originalKB = stat.size / 1024;

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
