const sharp = require('sharp');
const fs = require('fs');
const { stat } = fs.promises;
const [input, output] = process.argv.slice(2);

(async () => {
  try {
    const { size } = await stat(input); // in byte
    const originalKB = size / 1024;

    // nuova formula: più aggressiva per input > 1MB
    let quality = Math.round(90 - originalKB / 25);
    quality = Math.max(20, Math.min(quality, 90));

    const buffer = await sharp(input).webp({ quality }).toBuffer();
    await fs.promises.writeFile(output, buffer);

    console.log(`Converted: ${input} → ${output} (quality=${quality}, ${(buffer.length / 1024).toFixed(1)} KB)`);
    process.exit(0);
  } catch (err) {
    console.error(err.message);
    process.exit(1);
  }
})();
