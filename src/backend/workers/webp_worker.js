import sharp from 'sharp';
import fs from 'fs/promises';
import path from 'path';
import { AGGRESSIVITY_PROFILES } from '../media_processor.js';

const [input, output, aggressivityArg] = process.argv.slice(2);

if (!input || !output) {
  console.error('Usage: node webp_worker.js <input> <output> [aggressivity]');
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
    // Get aggressivity profile (default to 'standard')
    const aggressivity = aggressivityArg || 'standard';
    const profile = AGGRESSIVITY_PROFILES[aggressivity] || AGGRESSIVITY_PROFILES.standard;

    // Auto-calculate quality based on file size using aggressivity-modified formula
    const stat = await fs.stat(input);
    const originalKB = stat.size / 1024;

    // Formula: quality = Math.round(baseline - originalKB / divisor)
    let quality = Math.round(profile.formulaBaseline - originalKB / profile.formulaDivisor);
    quality = Math.max(15, Math.min(quality, 100));

    // Load image and get metadata
    const image = sharp(input);
    const metadata = await image.metadata();

    // Max dimension: 4K (3840px on longest side)
    const MAX_DIMENSION = 3840;
    const needsResize = metadata.width > MAX_DIMENSION || metadata.height > MAX_DIMENSION;

    // Resize if needed, maintaining aspect ratio
    let processedImage = image;
    if (needsResize) {
      processedImage = image.resize(MAX_DIMENSION, MAX_DIMENSION, {
        fit: 'inside',           // Fit within bounds, preserve aspect ratio
        withoutEnlargement: true // Don't upscale smaller images
      });
    }

    const info = await processedImage
      .webp({
        quality,
        effort: 6,
        smartSubsample: true,
        preset: 'photo',
        nearLossless: false
      })
      .toFile(output);

    console.log(
      `Converted [${aggressivity}]: ${input} → ${output} ` +
      `${needsResize ? `(resized from ${metadata.width}x${metadata.height}) ` : ''}` +
      `(quality=${quality}, ${(info.size / 1024).toFixed(1)} KB)`
    );

    process.exit(0);
  } catch (err) {
    await logError(err);
    process.exit(1);
  }
})();
