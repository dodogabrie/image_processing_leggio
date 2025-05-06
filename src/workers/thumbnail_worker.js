const sharp = require('sharp');
const fs = require('fs').promises;
const path = require('path');

async function main() {
  const [,, input, output, aliasOptions] = process.argv;
  if (!input || !output || !aliasOptions) {
    console.error('Usage: node thumbnail_worker.js <input> <output> <aliasOptions>');
    process.exit(1);
  }
  const opts = JSON.parse(aliasOptions);
  try {
    await fs.mkdir(path.dirname(output), { recursive: true });
    let img = sharp(input).resize(opts.size[0], opts.size[1], { fit: opts.crop ? 'cover' : 'inside' });
    img = img.toFormat(opts.format, { quality: opts.quality });
    await img.toFile(output);
    process.exit(0);
  } catch (err) {
    console.error('Thumbnail error:', err.message);
    process.exit(2);
  }
}

main();
